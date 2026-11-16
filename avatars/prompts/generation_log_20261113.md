# Image provenance

No other picture was given as input. Step A used text only and no input images. Each Step B call used only its matching Step A body as the character reference. Prompt file contents were concatenated verbatim in the requested order with two newline characters between them.

| File name | Prompt files used (in order) | Input image | Exact image tool name | Image model name reported | Date/time (UTC) | Attempts |
|---|---|---|---|---|---|---|
| raw/claude_body_raw.png | prompts/claude_body.txt + prompts/style_body.txt | none | image_gen.imagegen (callable: image_gen__imagegen) | not reported | 2026-11-13T06:44:29.978Z | 1 |
| raw/claude_head_raw.png | prompts/style_head.txt + prompts/claude_body.txt | raw/claude_body_raw.png | image_gen.imagegen (callable: image_gen__imagegen) | not reported | 2026-11-13T06:50:43.335Z | 3 |
| raw/codex_gpt_body_raw.png | prompts/codex_gpt_body.txt + prompts/style_body.txt | none | image_gen.imagegen (callable: image_gen__imagegen) | not reported | 2026-11-13T06:44:29.978Z | 1 |
| raw/codex_gpt_head_raw.png | prompts/style_head.txt + prompts/codex_gpt_body.txt | raw/codex_gpt_body_raw.png | image_gen.imagegen (callable: image_gen__imagegen) | not reported | 2026-11-13T06:51:05.254Z | 3 |
| raw/grok_body_raw.png | prompts/grok_body.txt + prompts/style_body.txt | none | image_gen.imagegen (callable: image_gen__imagegen) | not reported | 2026-11-13T06:44:57.045Z | 1 |
| raw/grok_head_raw.png | prompts/style_head.txt + prompts/grok_body.txt | raw/grok_body_raw.png | image_gen.imagegen (callable: image_gen__imagegen) | not reported | 2026-11-13T06:52:09.691Z | 3 |
| raw/deepseek_body_raw.png | prompts/deepseek_body.txt + prompts/style_body.txt | none | image_gen.imagegen (callable: image_gen__imagegen) | not reported | 2026-11-13T06:45:29.541Z | 1 |
| raw/deepseek_head_raw.png | prompts/style_head.txt + prompts/deepseek_body.txt | raw/deepseek_body_raw.png | image_gen.imagegen (callable: image_gen__imagegen) | not reported | 2026-11-13T06:51:27.038Z | 3 |

Visual checks passed for the saved outputs: plain backgrounds; no text, letters, logos or watermarks; full figures including shoes visible in bodies; two arms and hands in bodies; no extra limbs in heads (portrait cropping applies). Claude has rounded flower petals; GPT has no knot or interlaced-loop ornament; Grok has no blonde twin tails, hair bows or black-and-red gothic dress; DeepSeek has no whale or fish on the apron.

Dimension failure: all bodies are 1024x1536. All heads are 1254x1254 rather than the requested 1024x1024. Each head was regenerated twice with the same verbatim prompt and the same single matching body input; the tool returned 1254x1254 on all three attempts. The third attempt was saved without resizing. No further attempts were made.