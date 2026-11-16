# Avatar images: license and provenance

## License

The images in this folder (`*_512.png`, `*_body.png`), and the characters as they appear in the screenshots in `../docs/`, are licensed under the **Creative Commons Attribution 4.0 International license (CC BY 4.0)**. The full legal text is in [LICENSE](LICENSE), and the summary is at <https://creativecommons.org/licenses/by/4.0/>. The program code of this repository stays under GPL-3.0 (see `../LICENSE`).

Suggested attribution: *"AI Limits Monitor mascots" by P3anutSweet, CC BY 4.0, https://github.com/P3anutSweet/ai-limits-monitor*

These are unofficial project illustrations made with AI image tools. They are not official artwork, characters or marks of any AI vendor, and the project is not affiliated with any vendor. Some colors and accessories are loose nods to fan traits or product themes (for example a moon for Kimi and a whale for DeepSeek). If you think an image is too close to someone's mark or character, please open an issue.

## How each image was made

All prompts are in [prompts/](prompts/). The table lists prompt files and recorded inputs. Exact concatenation order and complete input history are established for the logged 2026-11-13 runs. Earlier rows summarize the retained asset records, with the limitations described below.

| Files | Made | Prompt files | Input image | Tool / model as recorded |
|---|---|---|---|---|
| `claude_body.png`, `codex_gpt_body.png`, `grok_body.png`, `deepseek_body.png` | 2026-11-13 | `<key>_body.txt` + `style_body.txt` | **none (text only)** | Codex `image_gen.imagegen` (OpenAI GPT image; model name not reported by the tool) |
| `claude_512.png`, `codex_gpt_512.png`, `grok_512.png`, `deepseek_512.png` | 2026-11-13 | `style_head_v4.txt` + `<key>_body.txt` | that character's own new full body (row above) | same as above |
| `deepseek_big_512.png` | 2026-11-13 | (none) | (none) | `deepseek_512.png` mirrored left-right |
| `gemini_512.png`, `qwen_512.png` | 2026-11-10 | `<key>_head.txt` + `style_head_gemini_set.txt` | **none (text only)** | Gemini image generation through an Antigravity agent (recorded as Gemini 3.1 Flash image) |
| `gemini_body.png`, `qwen_body.png` | 2026-11-10 | `<key>_body.txt` + `style_body.txt` | that character's own head (row above) | OpenAI GPT image through a Codex agent (model name not recorded) |
| `glm_body.png`, `kimi_body.png`, `minimax_body.png` | 2026-11-10 | `<key>_body.txt` + `style_body.txt` (`minimax_body.txt` includes its style) | **none (text only)** | OpenAI GPT image through a Codex agent (model name not recorded) |
| `glm_512.png`, `kimi_512.png`, `minimax_512.png` | 2026-11-10 | `style_head_v3.txt` + `<key>_head.txt` (`minimax_head.txt` includes its style) | GLM and Kimi: their own full body; MiniMax: none | same as above |

The 2026-11-13 rows are backed by a generation log ([prompts/generation_log_20261113.md](prompts/generation_log_20261113.md)). It records text-only prompts for the bodies, and each head made with only its own new body as input. These images replace an earlier Claude, GPT, Grok and DeepSeek set, which is not part of this repository.

The 2026-11-10 rows (Gemini, GLM, Kimi, Qwen, MiniMax) are reconstructed from the retained asset notes, prompt files and raw outputs. Complete invocation logs were not kept for them, so their full input history and the exact order in which the prompt parts were joined are not independently verified. The input images listed there are the ones the asset notes record. Nothing reviewed shows any other input image.

Post-processing: bodies were cut out of their flat grey background with `rembg` (`isnet-anime` model), trimmed and scaled to 900 px height; heads were scaled to 512 × 512. The monitor crops heads to a circle when drawing them.
