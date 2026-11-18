# Deployment (Cloud Run)

`.github/workflows/deploy-cloudrun.yml` runs on every push to `main` (or manually via *Run workflow*), and on pull requests against `main`, where only **test** runs:

1. **test** — `makemigrations --check --dry-run`, then `manage.py test` against the Compose MongoDB replica set.
2. **deploy** — build the image → push to Artifact Registry → `migrate` from that image against Atlas → deploy to Cloud Run → smoke-test `/` and `/businesses.geojson` (Doral bbox).

GitHub authenticates with **Direct Workload Identity Federation**; no service-account key exists anywhere. The running service uses its own least-privilege runtime service account.

## One-time setup

Replace `PROJECT_ID`, `PROJECT_NUMBER` and `REGION` (`us-east1` assumed below). Run these yourself; never paste secret values into files.

### GCP project

```bash
gcloud projects create PROJECT_ID
gcloud billing projects link PROJECT_ID --billing-account=BILLING_ACCOUNT_ID
gcloud services enable run.googleapis.com artifactregistry.googleapis.com \
  secretmanager.googleapis.com iamcredentials.googleapis.com --project=PROJECT_ID
gcloud projects describe PROJECT_ID --format='value(projectNumber)'   # → PROJECT_NUMBER
```

### Workload Identity Federation (GitHub → GCP)

```bash
gcloud iam workload-identity-pools create github \
  --project=PROJECT_ID --location=global --display-name="GitHub Actions"
gcloud iam workload-identity-pools providers create-oidc entr-community \
  --project=PROJECT_ID --location=global --workload-identity-pool=github \
  --attribute-mapping="google.subject=assertion.sub,attribute.repository=assertion.repository" \
  --attribute-condition="assertion.repository == 'alecoelhodev/entr-community'" \
  --issuer-uri="https://token.actions.githubusercontent.com"

WIF_MEMBER="principalSet://iam.googleapis.com/projects/PROJECT_NUMBER/locations/global/workloadIdentityPools/github/attribute.repository/alecoelhodev/entr-community"
```

### Artifact Registry, deploy access, runtime service account

```bash
gcloud artifacts repositories create entr-community \
  --repository-format=docker --location=REGION --project=PROJECT_ID
gcloud artifacts repositories add-iam-policy-binding entr-community \
  --project=PROJECT_ID --location=REGION \
  --member="$WIF_MEMBER" --role="roles/artifactregistry.writer"

gcloud projects add-iam-policy-binding PROJECT_ID \
  --member="$WIF_MEMBER" --role="roles/run.developer"

gcloud iam service-accounts create entr-community-runtime --project=PROJECT_ID
RUNTIME_SA="entr-community-runtime@PROJECT_ID.iam.gserviceaccount.com"
gcloud iam service-accounts add-iam-policy-binding "$RUNTIME_SA" \
  --project=PROJECT_ID --member="$WIF_MEMBER" --role="roles/iam.serviceAccountUser"
```

### MongoDB Atlas

1. Create a cluster in a region close to `REGION` (e.g. AWS `us-east-1` or GCP `us-east1`).
2. Create a database user with `readWrite` on `entr_community`, using a long random password.
3. **Network access:** Cloud Run and GitHub-hosted runners have no fixed egress IP, so add `0.0.0.0/0` and rely on credentials + TLS. For a real allowlist, route Cloud Run through a VPC connector + Cloud NAT with a reserved static IP (and run migrations from Cloud Run Jobs instead of the runner) — not set up here.
4. Copy the `mongodb+srv://…` connection string for the next step.

### Secrets

```bash
python3 -c 'import secrets; print(secrets.token_urlsafe(50), end="")' \
  | gcloud secrets create entr-django-secret-key --project=PROJECT_ID --data-file=-
read -rs MONGODB_URI && printf '%s' "$MONGODB_URI" \
  | gcloud secrets create entr-mongodb-uri --project=PROJECT_ID --data-file=- && unset MONGODB_URI

# Runtime reads both; CI reads only the URI (for migrations).
for SECRET in entr-django-secret-key entr-mongodb-uri; do
  gcloud secrets add-iam-policy-binding "$SECRET" --project=PROJECT_ID \
    --member="serviceAccount:$RUNTIME_SA" --role="roles/secretmanager.secretAccessor"
done
gcloud secrets add-iam-policy-binding entr-mongodb-uri --project=PROJECT_ID \
  --member="$WIF_MEMBER" --role="roles/secretmanager.secretAccessor"
```

### GitHub repository variables

These aren't secrets, so they're repo variables:

```bash
gh variable set GCP_PROJECT_ID --body PROJECT_ID
gh variable set GCP_REGION --body REGION
gh variable set GCP_WIF_PROVIDER \
  --body "projects/PROJECT_NUMBER/locations/global/workloadIdentityPools/github/providers/entr-community"
gh variable set CLOUD_RUN_HOST --body "entr-community-PROJECT_NUMBER.REGION.run.app"
gh variable set MAP_TILE_URL --body "https://…/{z}/{x}/{y}.png"   # optional, see below
# VPC_NETWORK / VPC_SUBNET: see "Redis (rate limiting)" below
```

`CLOUD_RUN_HOST` becomes `DJANGO_ALLOWED_HOSTS` and is the URL the smoke test hits. If you add a custom domain, update it there.

### First deploy and public access

Push to `main` or run the workflow manually. The **first** run creates the service, but it isn't publicly reachable yet, so the smoke test fails with a 403. Make it public once:

```bash
gcloud run services add-iam-policy-binding entr-community \
  --region=REGION --project=PROJECT_ID --member=allUsers --role=roles/run.invoker
```

Then re-run the workflow. The binding persists across later deploys. CI deliberately doesn't hold `run.admin`, so the workflow can't change who may invoke the service.

## Map tiles

OpenStreetMap's public tile servers [forbid heavy use](https://operations.osmfoundation.org/policies/tiles/), so production uses [MapTiler](https://www.maptiler.com/). If `MAP_TILE_URL` isn't set, the workflow falls back to OSM.

1. Create a MapTiler account and an API key. Under the key's allowed HTTP origins, enter the Cloud Run hostname as a bare domain, with no `https://` and no port: `entr-community-<project-number>.<region>.run.app`. Add `localhost` (no port) only if you want MapTiler locally. Never use `*.run.app`, which would allow every Cloud Run app.
2. Set the repo variable. The key is a publishable browser key, visible in page source by design, so a repo variable is the right home. Don't paste it into chat, commits or issues.
   ```sh
   gh variable set MAP_TILE_URL --body 'https://api.maptiler.com/maps/streets-v4/256/{z}/{x}/{y}.png?key=<KEY>'
   ```
3. Re-run the workflow.

The CSP `img-src` origin and the map attribution (`config/tiles.py`) both follow the tile host: `api.maptiler.com` gets "© MapTiler © OpenStreetMap contributors", and any other host gets the OSM attribution. A new provider that requires its own credit needs an entry there. Tile layers send `strict-origin-when-cross-origin` referrers so origin-restricted keys see the site's origin.

## Redis (rate limiting)

Rate limits (`config/ratelimit.py`) count in the Django cache, and Cloud Run runs several instances, so production needs a shared Redis. Settings refuse to boot on Cloud Run (`K_SERVICE` set) without `REDIS_URL`. The CI `migrate` step and local dev don't need one.

The infrastructure must exist **before** the workflow with Redis settings deploys, or the new revision fails to start (the old one keeps serving).

1. **Instance.** Memorystore for Redis, Basic tier, 1 GB (the minimum), same region as Cloud Run, AUTH and in-transit encryption on. This has a monthly cost (check the pricing page for `REGION`).
   ```bash
   gcloud services enable redis.googleapis.com --project=PROJECT_ID
   gcloud redis instances create entr-ratelimit --project=PROJECT_ID --region=REGION \
     --tier=basic --size=1 --redis-version=redis_7_2 --network=default \
     --enable-auth --transit-encryption-mode=server-authentication
   ```
2. **Secrets.** The URL holds the AUTH string, so it never touches the terminal history or a file:
   ```bash
   HOST=$(gcloud redis instances describe entr-ratelimit --region=REGION --project=PROJECT_ID --format='value(host)')
   gcloud redis instances describe entr-ratelimit --region=REGION --project=PROJECT_ID \
     --format='value(serverCaCerts[0].cert)' \
     | gcloud secrets create entr-redis-ca --project=PROJECT_ID --data-file=-
   printf 'rediss://:%s@%s:6378/0' \
     "$(gcloud redis instances get-auth-string entr-ratelimit --region=REGION --project=PROJECT_ID --format='value(authString)')" \
     "$HOST" | gcloud secrets create entr-redis-url --project=PROJECT_ID --data-file=-
   for SECRET in entr-redis-url entr-redis-ca; do
     gcloud secrets add-iam-policy-binding "$SECRET" --project=PROJECT_ID \
       --member="serviceAccount:$RUNTIME_SA" --role="roles/secretmanager.secretAccessor"
   done
   ```
   The workflow mounts the CA at `/etc/redis/ca.pem` (`REDIS_CA_FILE`) and injects `REDIS_URL`.
3. **Network.** Cloud Run reaches the private Memorystore IP through Direct VPC egress (`--vpc-egress=private-ranges-only`, so Atlas stays on the public path). The deploy principal needs to use the subnet:
   ```bash
   gcloud compute networks subnets add-iam-policy-binding default --region=REGION --project=PROJECT_ID \
     --member="$WIF_MEMBER" --role="roles/compute.networkUser"
   gh variable set VPC_NETWORK --body default
   gh variable set VPC_SUBNET --body default
   ```

**After the first deploy with Redis**, check that the client-IP key ignores spoofed headers: send 11 failed login POSTs to `/accounts/login/`, each with a different `X-Forwarded-For` value. The 11th must return 429. Then log in from a different network (e.g. a phone off Wi-Fi): it must **not** be 429. If it is, every visitor shares one counter and `client_ip` needs fixing.

## Gotchas

- **Migrations run before traffic shifts**, from the newly built image, so the serving revision briefly sees the new schema. Keep migrations additive and split destructive changes across two deploys.
- **The deploy action splits `env_vars` values on commas.** To pass several `DJANGO_ALLOWED_HOSTS`, escape each comma as `\,`.
- **A revision that crashes on boot never gets traffic.** The deploy step fails and the previous revision keeps serving. A missing `DJANGO_SECRET_KEY` or a bad `MONGODB_URI` shows up this way.
- **Static files are built into the image** by `collectstatic` in the Dockerfile and served by WhiteNoise with hashed names. A vendored file that references a missing sourcemap fails the image build.

## Rollback

```bash
gcloud run revisions list --service=entr-community --region=REGION --project=PROJECT_ID
gcloud run services update-traffic entr-community --region=REGION --project=PROJECT_ID \
  --to-revisions=REVISION_NAME=100
```

While traffic is pinned to a revision, new deploys may not receive it. Once a fix is deployed, run `gcloud run services update-traffic entr-community --region=REGION --to-latest`.
