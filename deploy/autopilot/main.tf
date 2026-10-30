terraform {
  required_providers { google = { source = "hashicorp/google", version = "~> 6.0" } }
}
variable "project" { type = string }
variable "region" { type = string
  default = "us-central1"
}
variable "image" { type = string }
variable "private_bucket" { type = string }
variable "public_bucket" { type = string }
variable "web_service_account" { type = string }
variable "runtime_env" { type = map(string)
  default = {}
}
# Map environment names to existing Secret Manager secret IDs, never secret values.
# Include AUTOPILOT_ADMIN_TOKEN on the web service separately, not this worker.
variable "secrets" { type = map(string) }
variable "autopilot_enabled" { type = bool
  default = false
}
variable "buffer_dry_run" { type = bool
  default = true
}
variable "live_publishing_validated" { type = bool
  default = false
}
variable "schedulers_paused" { type = bool
  default = true
}
# Free-tier budget: ~31 heavy minutes/day (see docs/scale-to-zero-deployment.md). The original
# schedule started the 4 vCPU job 68 times a day. Starts bill a 1-minute minimum each, so:
#   generate  renders one story per run and exits cheaply when the ready queue is full.
#   prepare   only recovers failed media delivery -> small job, twice a day.
#   schedule  creates the day's Buffer posts; later runs are idempotent.
#   retry     must stay dense inside the 18:00-19:00 IST window (needs >= 5 min lead).
#   verify    final reconciliation after the window; retry already verifies first.
# Original (cost-heavy) values: generate "0 9,11,13,15 * * *", prepare "10 10,12,14,16 * * *",
# schedule "*/10 16-18 * * *", verify "*/10 18-23 * * *", retry "5,15,25,35,45,55 18 * * *".
variable "autopilot_schedules" {
  type = map(string)
  default = {
    generate = "0 9,13 * * *"
    prepare = "10 10,14 * * *"
    schedule = "0 16,17,18 * * *"
    verify = "10 19,21 * * *"
    retry = "5,20,35,50 18 * * *"
  }
  validation {
    condition = toset(keys(var.autopilot_schedules)) == toset(["generate", "prepare", "schedule", "verify", "retry"])
    error_message = "autopilot_schedules must define exactly: generate, prepare, schedule, verify, retry."
  }
}
# A hung render must not burn days of free minutes: the 4 vCPU / 8 GiB job bills for its whole lifetime.
variable "render_timeout_seconds" { type = number
  default = 3000
}
provider "google" { project = var.project
  region = var.region
}
resource "google_service_account" "worker" { account_id = "her-autopilot-worker" }
resource "google_service_account" "scheduler" { account_id = "her-autopilot-scheduler" }
resource "google_project_iam_member" "database" {
  project = var.project
  role = "roles/datastore.user"
  member = "serviceAccount:${google_service_account.worker.email}"
}
resource "google_secret_manager_secret_iam_member" "read" {
  for_each = var.secrets
  project = var.project
  secret_id = each.value
  role = "roles/secretmanager.secretAccessor"
  member = "serviceAccount:${google_service_account.worker.email}"
}
resource "google_storage_bucket" "public" {
  name = var.public_bucket
  location = var.region
  uniform_bucket_level_access = true
  public_access_prevention = "inherited"
  force_destroy = false
}
resource "google_storage_bucket_iam_member" "public_read" {
  bucket = google_storage_bucket.public.name
  role = "roles/storage.objectViewer"
  member = "allUsers"
}
resource "google_storage_bucket_iam_member" "public_write" {
  bucket = google_storage_bucket.public.name
  role = "roles/storage.objectCreator"
  member = "serviceAccount:${google_service_account.worker.email}"
}
resource "google_storage_bucket_iam_member" "archive" {
  for_each = toset(["roles/storage.objectCreator", "roles/storage.objectViewer"])
  bucket = var.private_bucket
  role = each.value
  member = "serviceAccount:${google_service_account.worker.email}"
}
locals {
  job_env = merge(var.runtime_env, {
    GOOGLE_CLOUD_PROJECT = var.project,
    HER_PORTFOLIO_BUCKET = var.private_bucket,
    AUTOPILOT_PUBLIC_BUCKET = var.public_bucket,
    AUTOPILOT_ENABLED = tostring(var.autopilot_enabled),
    BUFFER_DRY_RUN = tostring(var.buffer_dry_run),
    AUTOPILOT_LIVE_VALIDATED = tostring(var.live_publishing_validated),
    HER_COMPUTE_BUDGET = "1"
  })
}
resource "google_cloud_run_v2_job" "autopilot" {
  name = "her-autopilot"
  location = var.region
  deletion_protection = true
  template {
    task_count = 1
    parallelism = 1
    template {
      service_account = google_service_account.worker.email
      max_retries = 0 # Paid generation is never replayed automatically by Cloud Run.
      timeout = "${var.render_timeout_seconds}s"
      containers {
        image = var.image
        command = ["python"]
        args = ["-m", "automation.autopilot_worker", "verify"]
        resources { limits = { cpu = "4", memory = "8Gi" } }
        dynamic "env" {
          for_each = merge(local.job_env, { HER_COMPUTE_WEIGHT = "1" })
          content { name = env.key
            value = env.value
          }
        }
        dynamic "env" {
          for_each = var.secrets
          content {
            name = env.key
            value_source { secret_key_ref { secret = env.value
              version = "latest"
            } }
          }
        }
      }
    }
  }
}
# Steps that never render video: schedule, verify, retry (Buffer/Firestore) and prepare (re-upload).
# Running them on a 1 vCPU / 2 GiB job avoids ~60 one-minute-minimum starts a day on
# the 4 vCPU / 8 GiB render job. Same image, service account, env and secrets.
resource "google_cloud_run_v2_job" "autopilot_light" {
  name = "her-autopilot-light"
  location = var.region
  deletion_protection = true
  template {
    task_count = 1
    parallelism = 1
    template {
      service_account = google_service_account.worker.email
      max_retries = 0
      timeout = "900s"
      containers {
        image = var.image
        command = ["python"]
        args = ["-m", "automation.autopilot_worker", "verify"]
        resources { limits = { cpu = "1", memory = "2Gi" } }
        dynamic "env" {
          for_each = merge(local.job_env, { HER_COMPUTE_WEIGHT = "0.25" })
          content { name = env.key
            value = env.value
          }
        }
        dynamic "env" {
          for_each = var.secrets
          content {
            name = env.key
            value_source { secret_key_ref { secret = env.value
              version = "latest"
            } }
          }
        }
      }
    }
  }
}
resource "google_cloud_run_v2_job_iam_member" "invoke_light" {
  for_each = toset([google_service_account.scheduler.email, var.web_service_account])
  project = var.project
  location = var.region
  name = google_cloud_run_v2_job.autopilot_light.name
  role = "roles/run.jobsExecutorWithOverrides"
  member = "serviceAccount:${each.value}"
}
resource "google_cloud_run_v2_job_iam_member" "invoke" {
  for_each = toset([google_service_account.scheduler.email, var.web_service_account])
  project = var.project
  location = var.region
  name = google_cloud_run_v2_job.autopilot.name
  role = "roles/run.jobsExecutorWithOverrides"
  member = "serviceAccount:${each.value}"
}
locals {
  schedules = var.autopilot_schedules
  # Only generate renders video (4 vCPU job). prepare re-uploads an already validated MP4
  # (download, hash, upload) and fits the 1 vCPU / 2 GiB job.
  step_job = {
    generate = google_cloud_run_v2_job.autopilot.id
    prepare = google_cloud_run_v2_job.autopilot_light.id
    schedule = google_cloud_run_v2_job.autopilot_light.id
    verify = google_cloud_run_v2_job.autopilot_light.id
    retry = google_cloud_run_v2_job.autopilot_light.id
  }
}
resource "google_cloud_scheduler_job" "step" {
  for_each = local.schedules
  name = "her-autopilot-${each.key}"
  region = var.region
  schedule = each.value
  time_zone = "Asia/Kolkata"
  paused = var.schedulers_paused
  attempt_deadline = "30s"
  retry_config { retry_count = 2
    min_backoff_duration = "60s"
    max_backoff_duration = "300s"
  }
  http_target {
    http_method = "POST"
    uri = "https://run.googleapis.com/v2/${local.step_job[each.key]}:run"
    headers = { "Content-Type" = "application/json" }
    body = base64encode(jsonencode({ overrides = { containerOverrides = [{ args = ["-m", "automation.autopilot_worker", each.key] }] } }))
    oauth_token { service_account_email = google_service_account.scheduler.email
      scope = "https://www.googleapis.com/auth/cloud-platform"
    }
  }
}
# Durable alerts are also emitted to Cloud Logging. Attach an email/Slack/etc.
# notification channel already configured by your organization.
variable "notification_channels" { type = list(string)
  default = []
}
resource "google_logging_metric" "failures" {
  name = "her_autopilot_failures"
  filter = "resource.type=\"cloud_run_job\" AND textPayload:\"AUTOPILOT_ALERT\""
  metric_descriptor { metric_kind = "DELTA"
    value_type = "INT64"
  }
}
resource "google_monitoring_alert_policy" "failures" {
  display_name = "ProjectHER Autopilot failure"
  combiner = "OR"
  notification_channels = var.notification_channels
  conditions {
    display_name = "Autopilot reported a failure"
    condition_threshold {
      filter = "metric.type=\"logging.googleapis.com/user/${google_logging_metric.failures.name}\" AND resource.type=\"cloud_run_job\""
      duration = "0s"
      comparison = "COMPARISON_GT"
      threshold_value = 0
      aggregations { alignment_period = "60s"
        per_series_aligner = "ALIGN_DELTA"
        cross_series_reducer = "REDUCE_SUM"
      }
    }
  }
}
