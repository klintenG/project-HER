import {Manifest} from "./news-types";
export const newsDefaults:Manifest = {
  "schema_version": "1.0",
  "content_mode": "news",
  "generation_id": "studio-default",
  "width": 1080,
  "height": 1920,
  "fps": 30,
  "duration_frames": 90,
  "seed": 42,
  "theme": {
    "paper": "#F2F0EC",
    "center": "#FAF9F6",
    "edge": "#DDDAD4",
    "text": "#505050",
    "secondary": "#686868",
    "font_semibold": "news-demo/Poppins-SemiBold.ttf",
    "font_bold": "news-demo/Poppins-Bold.ttf",
    "transition_frames": 10,
    "branding": ""
  },
  "input": {
    "original": "News explainer preview",
    "normalized": "News explainer preview",
    "kind": "supplied_account",
    "source_policy": "auto",
    "subject": "News explainer preview",
    "event_date": null,
    "entities": [],
    "places": [],
    "basis": "fictional",
    "assumptions": []
  },
  "evidence": {
    "sources": [
      {
        "id": "demo",
        "url": null,
        "title": "Studio placeholder",
        "retrieved_at": "",
        "published_at": null,
        "updated_at": null,
        "event_date": null,
        "authors": [],
        "text": "News explainer preview",
        "canonical_url": null
      }
    ],
    "claims": [
      {
        "id": "c1",
        "source_ids": [
          "demo"
        ],
        "text": "News explainer preview",
        "excerpts": {
          "demo": "News explainer preview"
        }
      }
    ],
    "conflicts": [],
    "unresolved": [],
    "verification": "fictional"
  },
  "script": {
    "summary": "News explainer preview",
    "narration": "News explainer preview",
    "sentences": [
      {
        "id": "s1",
        "text": "News explainer preview",
        "claim_ids": [
          "c1"
        ],
        "entity_ids": [],
        "phrase": "News explainer preview",
        "role": "hook",
        "emphasis": [],
        "headline_text": null
      }
    ],
    "entities": []
  },
  "audio": {
    "provider": "", "model": null, "fallbacks": [],
    "path": "news-demo/silence.wav",
    "duration": 3.0,
    "method": "sentence_clips",
    "quality": "Silent Studio placeholder",
    "script_hash": "007f0d6407895833eb9ea39a940f906a12f6465fdafdea6b62ce242c468556f5",
    "phrases": [
      {
        "sentence_id": "s1",
        "text": "News explainer preview",
        "start": 0.0,
        "end": 3.0
      }
    ],
    "words": []
  },
  "assets": [],
  "beats": [
    {
      "id": "b1",
      "start": 0,
      "end": 90,
      "sentence_ids": [
        "s1"
      ],
      "template": "text_bridge",
      "texts": [
        {
          "id": "t1",
          "text": "News explainer preview",
          "lines": [
            "News explainer preview"
          ],
          "rect": {
            "x": 0.13,
            "y": 0.38,
            "w": 0.74,
            "h": 0.25
          },
          "size": 76.0,
          "weight": 600,
          "reveal_frames": [
            0,
            0,
            0
          ],
          "emphasis": []
        }
      ],
      "layers": []
    }
  ],
  "events": [],
  "warnings": [],
  "stage_timings": {},
  "outputs": {}
};
