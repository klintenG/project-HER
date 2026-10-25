project = "project-her-510715"
region = "us-central1"
image = "us-central1-docker.pkg.dev/project-her-510715/cloud-run-source-deploy/project-her:AUTOPILOT_REVIEWED_TAG"
private_bucket = "project-her-510715-portfolio-output"
public_bucket = "project-her-510715-autopilot-media"
web_service_account = "793574023262-compute@developer.gserviceaccount.com"
autopilot_enabled = true
buffer_dry_run = false
live_publishing_validated = true
schedulers_paused = false
runtime_env = {
  AUTOPILOT_LLM_MODEL = "meta/meta-llama-3-70b-instruct"
  BUFFER_ORGANIZATION_ID = "6addc42752c2a07fde0c33db"
  BUFFER_INSTAGRAM_CHANNEL_ID = "6addcac02f1f5ed648c688f0"
  BUFFER_YOUTUBE_CHANNEL_ID = "6addce342f1f5ed648c69f1e"
  # Copy the existing production non-secret creative-engine settings here.
  # Do not change active image or narration models to enable Autopilot.
}
secrets = {
  REPLICATE_API_TOKEN = "her-provider-replicate-token"
  GEMINI_API_KEY = "existing-gemini-secret-id"
  BUFFER_API_KEY = "her-provider-buffer-key"
}
notification_channels = [] # Add an existing Cloud Monitoring notification channel.
