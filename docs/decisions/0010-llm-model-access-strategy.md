# 0010. LLM Model Access Strategy: Pre-trained Models via Managed Inference API

- Status: Proposed
- Date: 2026-06-16

## Context

ADRs 0007, 0008, and 0009 define up to six LLM invocations per workflow event across four distinct service types:

| Service | Decision Type | Invocations per first-seen event |
| --- | --- | --- |
| Workflow Actions LLM Decision Service | Abstract orchestration plan generation | 1 (top-level planner, runs first) |
| Delivery Targets LLM Decision Service | Routing and eligibility determination | 1 (named step in plan) |
| Field Mapping LLM Decision Service | Structured JSONata generation and placeholder creation | 2 (once per loop) |
| Field Synthesis LLM Decision Service | Natural language credential content generation | 2 (once per loop) |

For repeat events where the credential template is already stored, Loop 1 is skipped and the count drops to four invocations. The plan itself may also be cached per ADR 0009, reducing invocations further for repeat event patterns.

Each service has a meaningfully different reasoning profile:

- **Workflow Actions** performs open-ended conditional planning over event context and available services. It must reason about which steps to include, reorder, or skip — a task that requires strong instruction-following and multi-step reasoning.
- **Delivery Targets** performs eligibility and routing reasoning over structured policy and learner context. The output schema is relatively constrained: a small set of selected targets with confidence and rationale.
- **Field Mapping** produces machine-executable JSONata expressions. Structural precision matters more than fluency; an expression with a subtle syntax error breaks the pipeline.
- **Field Synthesis** generates natural language content for badge fields such as achievement descriptions and alignment rationale. Fluency and relevance matter; the output is human-facing.

These distinct profiles mean a single model configuration may not produce optimal results across all invocations. This ADR addresses how those models are accessed, not the final model selection per service — those assignments are provisional and expected to evolve through POC experimentation.

Three fundamental approaches exist for running LLM-based services:

1. **Train custom models** — collect domain-specific labeled examples, train dedicated models for each decision type
2. **Fine-tune pre-trained models** — take an existing instruction-tuned model and adapt it using domain-specific examples
3. **Use pre-trained models as-is** — use publicly available instruction-tuned models with zero-shot or few-shot prompting

The POC is expected to complete by the end of July 2026, approximately six weeks from the date of this ADR. The primary goal of the POC is to validate that LLM-assisted orchestration and transformation produce structurally sound and semantically reasonable outputs — not to optimize model performance for production.

The project is deployed on AWS. Amazon Bedrock was identified in earlier architecture discussions as the natural model access platform given the AWS context. The DCC Credential Co-Writer project — which is the explicit model for Loop 1 of the Transformation Mappings pipeline (ADR 0008) — selected `microsoft/Phi-4-mini-instruct` for badge content generation tasks. That model, and the other open-source candidates evaluated by DCC (Phi-3.5-mini, Qwen3-4B, Gemma-3-4b), carry MIT or Apache 2.0 licenses but are not currently available in the Amazon Bedrock model catalog.

## Decision Drivers

- POC timeline of approximately six weeks rules out training data collection, model training, and fine-tuning pipelines
- The POC's goal is validating whether the architecture and AI capabilities work — optimizing model performance comes after the baseline is proven
- Multiple services with different reasoning profiles may benefit from different model choices; the architecture should accommodate this without service redesign
- AWS-native deployment preference: consistent authentication (IAM), logging (CloudWatch), and operational patterns
- The DCC Credential Co-Writer connection creates a natural comparison point for Field Mapping and Field Synthesis output quality
- Model selection should be revisable independently per service; prompt engineering and model choices should not be tangled with service logic
- As an open-source project, preferring open-source models where quality is comparable supports the project's public-good alignment; this preference should be honored where feasible but does not override the POC timeline constraint

## Decision

**The project will use pre-trained, instruction-tuned models accessed via managed inference API. No custom training or fine-tuning will be performed for the POC.**

**Amazon Bedrock will serve as the primary model access platform.** Each LLM Decision Service will communicate with models through the Bedrock Converse API, which provides a unified message-passing interface across all Bedrock-hosted models. Switching between Claude, Llama, Mistral, or other Bedrock-hosted models requires only a model ID configuration change, not an application code change.

**Each LLM Decision Service will interact with the model through a thin provider adapter.** The adapter presents a simple interface — given a system prompt, a list of messages, and generation parameters, return a response — with no model-specific logic in the service itself. The adapter implementation targets Bedrock for the POC but can be swapped per service independently if a model outside the Bedrock catalog proves necessary.

**Initial model assignments are provisional.** All services will begin with the same model to establish an end-to-end working pipeline. Per-service differentiation follows once the baseline is running and output quality can be evaluated per decision type.

**The POC will capture structured per-invocation metadata for every LLM call.** Each invocation record includes at minimum: event ID, service name, loop/phase identifier, model ID, provider, temperature, input token count, output token count, latency, confidence score, and rationale. The adapter captures this metadata and returns it as part of the step result; the Orchestration Service (ADR 0011) stores it in its unified execution log alongside other step data and exposes it through the Orchestrator's read API. Admin UI access to LLM invocation data flows through the same read path as all other execution trace data, consistent with ADR 0011's "no standalone logging microservice" constraint.

Per-invocation metadata capture is non-optional: it is the primary mechanism for systematic model comparison at the end of the POC. Access controls and log retention policy for rationale strings (which may contain learner data fragments) should be addressed in the Orchestration Service execution log design, not here.

**Each LLM Decision Service output schema must include confidence and rationale fields.** The POC requirements specify that LLM Decision Services produce confidence scores and decision rationale. These are not separate features — they are part of the structured output schema the model is asked to produce for every invocation. The adapter enforces a JSON schema on model responses that includes `confidence` (a 0–1 score the model assigns to its own output) and `rationale` (a brief natural-language explanation). This is a prompt engineering and structured output contract concern, not a model access concern; it applies equally regardless of which model or platform is used. Bedrock's `toolUse` feature, the Anthropic and OpenAI tool-calling APIs, and HuggingFace's structured generation all support schema-enforced JSON output.

This ADR records one architectural decision, not two. The training approach, the platform choice, and the abstraction design are all answers to the same question: how do we run the LLMs defined in ADRs 0007, 0008, and 0009? They are decided together because the platform choice constrains available models and the model selection informs whether an abstraction is needed. Separating them into multiple ADRs would create artificial ordering and cross-referencing overhead without meaningful benefit.

## Options Considered

### Training approach

| Option | Description | Assessment |
| --- | --- | --- |
| Train custom models from scratch | Collect labeled examples for each decision type; train dedicated models | Requires labeled training data (currently unavailable), ML engineering resources, compute infrastructure, and months of timeline. Not feasible for the POC. |
| Fine-tune pre-trained models | Take an instruction-tuned model; fine-tune on domain-specific examples for each service | More feasible than training from scratch but still requires labeled examples per task, a fine-tuning pipeline, and evaluation infrastructure. Not feasible within six weeks; deferred to post-POC. |
| Pre-trained models as-is (chosen) | Use publicly available instruction-tuned models with zero-shot or few-shot prompting | Immediately usable; appropriate for a POC whose goal is architecture validation over model optimization. |

### Model access platform

Three clarifications on the model landscape before the options table:

- **Anthropic Claude models (Haiku, Sonnet, Opus) are available on Bedrock.** Using Bedrock does not mean forgoing Anthropic models — it is the AWS-native way to access them. Testing Anthropic models does not require a direct Anthropic API integration.
- **OpenAI GPT models are not on Bedrock.** Accessing GPT-4o, GPT-4.1, or other OpenAI models requires either the OpenAI API directly or Azure OpenAI. These are separate providers with separate credentials.
- **Google Gemini models are not on Bedrock.** Accessing Gemini requires Google AI Studio or Vertex AI — a separate Google Cloud account and credential set.

| Option | Description | Main concern |
| --- | --- | --- |
| Amazon Bedrock (chosen) | AWS-managed inference service; unified Converse API covers Claude (Anthropic), Llama (Meta), Mistral, and others | Phi-4-mini, Qwen3-4B, Gemma — the DCC open-source candidates — are not in the Bedrock catalog; OpenAI GPT and Google Gemini models also require separate providers |
| OpenAI API (direct) | GPT-4o, GPT-4.1-mini, and other OpenAI models; strong structured output via function calling | Requires separate API key management outside AWS IAM; observability via OpenAI's platform rather than CloudWatch; adds a third-party dependency |
| Google AI / Vertex AI | Access to Gemini Flash, Gemini Pro; strong performance on education data tasks observed in adjacent research | Requires Google Cloud account and credentials; adds significant operational complexity for a project already on AWS; not AWS-native |
| Hugging Face Inference Endpoints | Broad open-source catalog including Phi-4-mini, Qwen3, and Gemma; aligns with the project's open-source orientation | Separate account, billing, and credential management outside AWS; endpoint lifecycle management is manual; not AWS-native |
| Self-hosted on AWS (SageMaker, EC2) | Full control; any open-source model; no external API dependencies; best long-term alignment with open-source project goals | Significant infrastructure work to provision, operate, and scale; inappropriate for a six-week POC timeline, but the most appropriate path for production-scale open-source deployment |
| LiteLLM (abstraction-first) | Open-source proxy layer normalizing multiple provider APIs; enables multi-provider testing from one interface | Introduces a running service dependency; overhead not justified until the project is actively managing multiple providers |

## Why Pre-trained Models

Training a model from scratch requires: labeled training data for each of the four decision types, an ML engineering pipeline, compute infrastructure, an evaluation framework, and iteration cycles to achieve acceptable quality. None of these are available on the POC timeline, and the project does not currently have labeled examples for any of the four decision types — that data would itself be generated by running the POC.

Fine-tuning is more tractable but has the same data dependency. The right time to consider fine-tuning is after the POC has demonstrated that the architecture works and has produced a corpus of labeled outputs that can be used as training examples. Fine-tuning an underperforming service after POC completion is explicitly supported by the provider adapter design.

Pre-trained instruction-tuned models are mature enough to test the architecture meaningfully. If prompt engineering produces acceptable results, the POC goal is met. If it does not, the POC provides evidence of where quality falls short, which informs a targeted fine-tuning plan.

## Why Amazon Bedrock

Amazon Bedrock is AWS's managed inference service. It provides API access to pre-trained models from multiple providers — it does not offer model training. Key operational properties that justify it as the POC platform:

**AWS-native authentication and logging.** Bedrock uses the same AWS IAM credentials as all other AWS services. There are no separate API keys to manage, rotate, or store in a secrets manager. Model invocations log to CloudWatch using the same patterns as Lambda, SQS, and other services already in the architecture. This consistency reduces operational overhead and keeps the observability surface unified.

**Bedrock Converse API.** The Converse API accepts a standard message format (system prompt + conversation turns) and returns a standard response regardless of which model is invoked. Switching from Claude Haiku to Llama 3.1 8B to Mistral requires changing only the `modelId` parameter. No application code changes are required. This is the primary mechanism that makes per-service model differentiation low-cost.

**Model variety without additional accounts.** Claude (Haiku, Sonnet, Opus), Meta Llama (8B, 70B, 405B), Mistral, Amazon Titan, and others are all accessible within one AWS account. The POC can try different models for different services without setting up credentials or billing relationships with multiple providers.

**The DCC model catalog mismatch is accepted.** Phi-4-mini-instruct, Qwen3-4B, and Gemma-3-4b are not on Bedrock. They are available via Azure AI (Phi models), Hugging Face Inference Endpoints (all three), or local hosting via Ollama. If post-POC quality or cost analysis shows that a Bedrock-hosted model is insufficient for a specific service — particularly Field Mapping, which is the DCC analogue — the provider adapter makes switching to a HuggingFace-hosted or Azure-hosted model a per-service configuration change. The mismatch does not block the POC.

## Known Model Performance Context by Task Type

The four LLM Decision Service types map onto distinct task categories. Where available, empirical findings from AI-assisted education data research inform the characterizations below. The quantitative claims in the JSONata generation section are drawn from an empirical study on AI-assisted schema mapping and JSONata generation in the LIF/education domain conducted by researchers working in this area. The characterizations of Delivery Targets, Field Synthesis, and Workflow Actions draw on general LLM capability research and reasoning about task type rather than domain-specific benchmarks; the research surveyed does not include studies directly measuring LLM performance on credential routing decisions or open badges content generation as isolated tasks. This section should be revisited if more targeted benchmarks become available. Model names in this section are illustrative of tier; exact model versions change frequently.

### JSONata generation (Field Mapping service)

Research on AI-assisted JSONata generation for education schema mapping shows that **smaller, cheaper models match or outperform larger frontier models on this specific task** — a counterintuitive result. Claude Haiku-class models achieve JSONata validity pass rates in the 96–97% range. Gemini Flash-class models achieve 98%. Larger frontier models (Claude Sonnet, GPT-5.2-class) actually score slightly lower (91–95%) while costing significantly more per invocation. The working hypothesis is that JSONata generation is a pattern-recognition task that benefits from the focused, fast generation of smaller models rather than the broader reasoning of larger ones.

This finding suggests that the Field Mapping service should **not** be the first candidate for upgrading to a more expensive model if initial quality is low. Prompt engineering is more likely to help than a model upgrade.

Published code generation research offers partial corroboration for the principle that architectural quality can outweigh raw parameter count: StarCoder2-15B matches or outperforms CodeLlama-34B on standard code completion benchmarks despite being less than half the size (Lozhkov et al., "StarCoder 2 and The Stack v2", arXiv:2402.19173, 2024). More broadly, benchmarks across the SLM tier (0.4B–10B parameters) show that architecture and training quality matter more than parameter count alone within a model generation — some 1.3B models outperform 7B models in the same tier. However, the same benchmarks confirm that the gap between SLM-range models and frontier-class models (70B+, GPT-4/Claude Sonnet class) on broad code generation tasks is real: "achieving further improvements in accuracy requires switching to larger models" (arXiv:2507.03160). The domain-specific JSONata result above should be understood as task-specific, not a general rule that small models beat large ones on code generation.

### Sink system routing (Delivery Targets service)

The Delivery Targets service decides which downstream sink systems — for example, LearnCard Wallet, SmartResume, or both — should receive a transformed credential for a given event. This is a classification and eligibility-reasoning task, not a schema mapping task: the model receives event type, learner context, policy context, and the set of available delivery targets, and must determine which of them are applicable given the circumstances.

There is no directly analogous benchmark in the adjacent research surveyed for this ADR. The task is most similar to constrained decision-making under uncertainty with a small output space (selecting a subset from a small enumerated set of targets). Small models are likely adequate for this task given the constrained output and the relatively clear conditional logic involved, but this is an assumption that the POC should validate. If the Delivery Targets service produces low-confidence or inconsistent routing decisions, the most informative next step is examining whether the policy context and available-targets enumeration are being presented clearly to the model, rather than immediately upgrading model tier.

### Natural language generation (Field Synthesis service)

For natural language generation of human-facing content (badge descriptions, alignment rationale, achievement summaries), quality differences between model tiers are more visible to human reviewers and harder to quantify with automated metrics. This is the task type where a Sonnet-class model most clearly outperforms Haiku-class, and where open-source small models show wider variance. Field Synthesis is the best candidate for a model upgrade if baseline quality is insufficient.

### Complex conditional planning (Workflow Actions service)

Multi-step conditional reasoning — deciding which workflow steps to include, reorder, or skip — is the task type most sensitive to model reasoning capability. There is no directly analogous education data benchmark. This is the task type where larger frontier models are expected to have a clearer advantage over smaller ones, and where model tier should be the first variable to adjust if plan quality is insufficient.

### Implication for the POC

The task-type breakdown suggests that **not all services should be upgraded together** when quality problems emerge. The Field Mapping service should exhaust prompt engineering before trying a larger model; the Workflow Actions service should be the first to try a larger model if quality is low. Logging model ID, token count, latency, and per-invocation confidence scores from the start of the POC provides the data needed to make these decisions systematically rather than by intuition.

### Open-source model considerations for this project

As an open-source project, there is a meaningful long-term argument for preferring open-source models: contributors and institutions should be able to run the system without commercial API dependencies. The open-source models evaluated for adjacent tasks in this domain — Llama 4 (Meta, available on Bedrock), Phi-4-mini-instruct (Microsoft, MIT license, via HuggingFace or Azure), and Qwen3-4B (Alibaba, Apache 2.0, via HuggingFace) — are competitive with frontier commercial models for the structured output tasks (Field Mapping, Delivery Targets) and somewhat behind on the open-ended reasoning and generative tasks (Workflow Actions, Field Synthesis). For the POC, using Bedrock-hosted Llama models (Llama 3.1 8B or Llama 3.3 70B) where Haiku is the baseline gives comparable quality while staying on an open-source model. Post-POC, self-hosted open-source models on SageMaker or EC2 represent the path toward removing commercial API dependencies entirely.

## Provider Adapter Design

Each LLM Decision Service delegates all model communication to a provider adapter. The adapter:

1. Accepts a structured prompt (system message + user messages) and generation parameters
2. Translates to the target API format (Bedrock Converse API for the POC)
3. Returns a structured response that always includes the primary decision output, a confidence score, and rationale

### Generation parameters

Two parameters are worth defining here because they affect output quality differently per service type:

**Temperature** controls how deterministic vs. creative the model's output is, on a scale of roughly 0 to 1. At temperature 0, the model always picks the highest-probability next token — the output is consistent across repeated calls with the same input. Higher temperatures introduce randomness, producing more varied results. For the Field Mapping service, low temperature (near 0) is appropriate because JSONata expressions must be syntactically correct and reproducible. For the Field Synthesis service, slightly higher temperature (0.3–0.7) may produce more natural-sounding and varied badge content. Temperature is a per-service configuration; the adapter accepts it as a parameter.

**Max tokens** caps the length of the model's response. Setting it appropriately per service type prevents runaway generation and controls cost.

### Confidence and rationale as structured output

The POC requirements specify that LLM Decision Services produce confidence scores and decision rationale. These are not separate API calls or post-processing steps — they are fields in the JSON schema the adapter enforces on every model response. Every service's output schema includes at minimum:

```json
{
  "result": <service-specific output>,
  "confidence": 0.87,
  "rationale": "Brief explanation of why this decision was made and what uncertainty remains"
}
```

The model generates the `confidence` value and `rationale` text as part of its response, based on its own assessment of the task. This is the verbalized confidence approach: the model does not have a true internal probability score, but research (Kadavath et al., "Language Models (Mostly) Know What They Know", arXiv:2207.05221, 2022) has shown that models can often accurately assess their own uncertainty when asked directly. Verbalized confidence is widely used in practice because it requires no special API support and works across providers.

Two more principled alternatives exist but are not used in the POC:

- **Log probabilities**: Some model APIs expose token-level log probabilities that can be aggregated into a confidence estimate. This is more mathematically grounded but is not consistently available across all Bedrock-hosted models, and requires non-trivial implementation work.
- **Consistency sampling**: Running the same prompt multiple times and measuring agreement between outputs provides an empirically reliable confidence signal. It multiplies per-decision cost by the number of samples (typically 3–5) and is not appropriate for the latency profile of this system.

The known limitation of verbalized confidence is that models tend toward overconfidence — self-reported scores cluster high. If confidence scores are used for automated thresholding decisions (e.g., routing low-confidence outputs to human review), the POC should treat raw scores as ordinal rather than calibrated probabilities and validate the threshold empirically against observed outputs.

The adapter enforces this schema using the structured output features available on each provider:
- **Bedrock**: `toolUse` feature with a defined input schema
- **Anthropic direct API**: tool-calling with `tool_choice: required`
- **OpenAI API**: `response_format: { type: "json_schema" }` or function calling
- **HuggingFace**: structured generation via Outlines or similar

The Field Mapping service is a special case: its primary output is a JSONata expression string, not a JSON object. The adapter wraps the expression in a JSON envelope (`{ "expression": "...", "confidence": ..., "rationale": "..." }`) so that schema enforcement still applies and the expression is returned as a string field.

### Multi-provider design

The adapter interface should be defined as a simple protocol or abstract class. For the POC, one implementation is provided targeting Bedrock. Additional implementations — OpenAI API, HuggingFace Inference Endpoints, Anthropic direct API, Ollama — can be added per-service without changing service logic. The intent is that any service can point at any adapter implementation via configuration; no cross-service changes are required when switching a single service's model or provider.

This is intentionally not LiteLLM. LiteLLM is a capable multi-provider abstraction, and adopting it as the implementation of the provider adapter is explicitly supported if managing multiple providers becomes complex. The adapter interface should be compatible with a LiteLLM-backed implementation so the migration path is straightforward.

## Provisional Model Assignments

All services will begin with one model to establish an end-to-end working pipeline. Per-service differentiation follows once the full pipeline is running and output quality per service can be assessed.

Two reasonable starting points are offered. The Anthropic Claude option is the simplest to start with if the team wants to reduce variables during initial wiring. The open-source Llama option is preferable if the project's open-source alignment should be honored from the start; Llama 3.1 8B is on Bedrock and requires no additional accounts.

| Service | Anthropic baseline | Open-source baseline | First escalation if quality is low |
| --- | --- | --- | --- |
| Workflow Actions | Claude Haiku (Bedrock) | Llama 3.1 8B (Bedrock) | Claude Sonnet or Llama 3.3 70B — this is the task type most sensitive to model reasoning capability |
| Delivery Targets | Claude Haiku (Bedrock) | Llama 3.1 8B (Bedrock) | Prompt engineering before model upgrade; research suggests small models are near the ceiling for this task type |
| Field Mapping (both loops) | Claude Haiku (Bedrock) | Llama 3.1 8B (Bedrock) | Prompt engineering first; research on analogous JSONata tasks shows smaller models match larger ones — a model upgrade is unlikely to help more than prompt iteration |
| Field Synthesis (both loops) | Claude Haiku (Bedrock) | Llama 3.1 8B (Bedrock) | Claude Sonnet or Llama 3.3 70B — this is the task type where quality differences between model tiers are most human-visible |

**If Field Mapping JSONata validity is systematically low** after prompt engineering, the next candidates are Phi-4-mini-instruct (MIT license, HuggingFace or Azure AI) and Llama 3.3 70B (Bedrock). Both have shown strong structured output quality in adjacent research. The provider adapter makes this a per-service configuration change with no impact on other services.

**If the team wants to test OpenAI or Gemini models** — which have not been benchmarked for this specific use case in this domain — the provider adapter accommodates this. An OpenAI adapter requires the OpenAI API key and a separate implementation; a Google AI adapter requires a Google Cloud account and a separate implementation. Both are feasible, but neither is a priority over getting the Bedrock baseline running. If the team wants to do systematic model comparison across providers, structuring that as a dedicated POC experiment (same prompts, same inputs, different adapters) will produce the most useful data.

## Relationship to Training and Fine-tuning Post-POC

The POC will generate real examples of inputs and outputs for each of the four decision types. These examples are the raw material for post-POC fine-tuning if pre-trained model quality proves insufficient. The most likely candidates for fine-tuning are:

- **Field Mapping**, where JSONata correctness is critical and systematic prompt engineering may not fully compensate for model limitations on this specialized output format
- **Delivery Targets**, where policy-conformant routing decisions may benefit from domain-specific examples if zero-shot accuracy is low

If fine-tuning is pursued, the provider adapter architecture supports it: a fine-tuned model is accessed through the same adapter interface as its base model; the service code does not change.

## Consequences

### Positive

- Zero lead time to first LLM invocation: no training data collection, no model hosting setup, no fine-tuning pipeline
- Bedrock Converse API handles model API differences; switching models is a `modelId` configuration change
- AWS IAM authentication and CloudWatch logging are consistent with the rest of the infrastructure
- Per-service provider adapters allow models to be swapped independently per service without cross-service changes
- POC output provides real labeled examples that can drive targeted fine-tuning post-POC, with evidence of which services need it most
- Per-invocation metadata logging (model ID, token counts, latency, confidence, rationale) is built in from the start, enabling systematic model comparison analysis at the end of the POC
- LLM invocation metadata flows through the Orchestration Service's unified execution log and read API (ADR 0011), supporting the admin UI decision-review use case without a parallel observability stack
- The provisional baseline (all services on one model) is immediately runnable; differentiation is optional and incremental

### Negative

- The open-source small models validated by DCC for badge content tasks (Phi-4-mini, Qwen3-4B, Gemma-3-4b) are not on Bedrock; accessing them requires a separate provider
- Per-invocation cost with frontier models (Claude Haiku, Llama 70B) is higher than with small open-source models; acceptable for a POC but potentially significant at production event volume
- Pre-trained prompting typically exhibits higher output variance than fine-tuned models; output quality for JSONata generation in particular may be less consistent than DCC's experience with Phi-4-mini fine-tuned for that task
- Bedrock model versioning is managed by AWS; behavior may change when AWS updates model versions
- Invocation log records will contain rationale strings that may include learner data fragments; access controls and retention policy for this data should be addressed in the Orchestration Service execution log design before the POC processes real learner data

### Revisit Triggers

This decision should be revisited if:

- Pre-trained model output quality is systematically insufficient for any service after reasonable prompt engineering effort; fine-tuning scope should then be defined for that service
- Per-invocation cost at projected event volume is prohibitive; open-source models hosted on AWS SageMaker should then be benchmarked
- The Field Mapping service's JSONata output is unreliable with Bedrock-hosted models, and Phi-4-mini-instruct produces significantly better results; the provider adapter supports this substitution without service redesign
- Amazon Bedrock adds Phi-4-mini, Qwen3, or comparable small open-source models to its catalog; model selection should be revisited at that point
- A decision is made to move toward on-premise or air-gapped deployment; self-hosted open-source models become mandatory in that scenario

## Open Questions

- What temperature should each service type use? Temperature is a generation parameter (0–1) controlling how deterministic vs. varied the model's output is. At 0 the model always picks the most probable next word, producing consistent and precise output — appropriate for Field Mapping (JSONata must be syntactically exact) and Delivery Targets (routing decisions should be reproducible). Higher values introduce randomness and variety — appropriate for Field Synthesis, where natural-sounding badge descriptions benefit from some variation. Recommended starting points: Field Mapping and Delivery Targets at 0.1 or lower; Field Synthesis at 0.3–0.5; Workflow Actions at 0.2 (plans should be consistent but allow some contextual flexibility). These should be tunable per-service via configuration.
- What max-token limits are appropriate per service, and how do they interact with confidence/rationale overhead? The structured output envelope adds tokens beyond the core decision output; max-token limits must account for this.
- Should a local development fallback using Ollama (running Llama or another compatible model locally) be supported for development and testing without AWS credentials? This would allow contributors to run the pipeline locally without a Bedrock account, which matters for an open-source project where external contributors may not have access to the project's AWS environment.
- What Bedrock model invocation quotas apply to the AWS account, and do any quotas need to be raised before POC work begins?
- Should the POC include at least one systematic model comparison experiment — running the same prompts and inputs through multiple adapters (Bedrock Llama, Claude Haiku, and optionally an OpenAI or Gemini model) for one service — to produce empirical data on model quality for this specific domain? Even a small experiment on Field Mapping JSONata validity would be more informative than assumptions.
- Log retention period, data minimization for rationale strings (which may contain learner data fragments), and access controls for LLM invocation data in the admin UI are deferred to the Orchestration Service execution log design.

## References

- [ADR 0007: LLM Decision Service Decomposition](0007-llm-decision-service-decomposition.md)
- [ADR 0008: Transformation Mapping Service Decomposition](0008-transformation-mapping-service-decomposition.md)
- [ADR 0009: Workflow Actions Orchestration Model](0009-workflow-actions-orchestration-model.md)
- [ADR 0011: Orchestration Runtime Technology](0011-orchestration-runtime-technology.md)
- [DCC Credential Co-Writer (Live Tool)](https://co-writer.dcconsortium.org/)
- [Skills Mobility Infrastructure POC Requirements](../2_requirements/poc-requirements.md)
- Kadavath et al., "Language Models (Mostly) Know What They Know", arXiv:2207.05221, 2022 — foundational verbalized confidence study; LLMs can self-assess uncertainty when prompted directly
- Lozhkov et al., "StarCoder 2 and The Stack v2", arXiv:2402.19173, 2024 — StarCoder2-15B matches or outperforms CodeLlama-34B on code completion benchmarks; supports architecture > raw parameter count claim
- "A Comprehensive Study of Small Language Models for Code Generation", arXiv:2507.03160 — benchmarks SLMs (0.4B–10B) on code generation; finds architecture/training quality matters more than parameter count within the SLM tier, and that frontier models retain an accuracy advantage for broader tasks
