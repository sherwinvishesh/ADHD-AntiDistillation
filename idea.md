# ADHD: Adaptive Defense via Honeypot Deception

## Project Idea and Design Rationale

## 1. The Core Idea

ADHD, short for **Adaptive Defense via Honeypot Deception**, is a defensive framework for protecting capable AI models from unauthorized knowledge distillation through public or semi-public interfaces.

The project begins from a difficult observation: once a model is exposed through an API, an attacker does not need access to its weights in order to learn from it. The attacker can repeatedly query the model, collect prompt and response pairs, and use those outputs as supervision for another model. If the source model produces detailed explanations, worked solutions, code, proofs, analyses, and other structured outputs, then those responses can become a valuable synthetic training set.

ADHD does not try to make model outputs impossible to collect. That is not realistic for a useful API. Instead, it changes the defensive objective.

The central idea is:

> If an attacker is going to collect responses anyway, make the collected responses much less useful as training material while keeping them useful to a human reader.

The desired protected response therefore has two different audiences with two different outcomes.

For a legitimate human user, the response should remain correct, coherent, understandable, and practically useful.

For a student model trained on a large collection of protected responses, the explanation should provide inferior reasoning supervision. It should encourage inefficient, brittle, unnecessarily complicated, or otherwise undesirable problem-solving habits rather than clean and generalizable reasoning patterns.

The final answer is not supposed to be corrupted. The useful content is not supposed to disappear. The protection is aimed at the **training value of the reasoning path**, not at the correctness of the final result.

This is the defining idea behind ADHD.

## 2. The Problem ADHD Is Trying to Solve

Modern model extraction is not limited to copying facts or memorizing exact outputs. A sufficiently large collection of high-quality model responses can teach a smaller model patterns of behavior that transfer beyond the original examples.

A detailed response can teach a student model things such as:

1. How to decompose a problem.
2. Which intermediate variables to introduce.
3. Which mathematical operation to perform first.
4. Which proof strategy is appropriate.
5. Which algorithmic structure is efficient.
6. Which pieces of evidence matter in an analysis.
7. Which assumptions are safe to make.
8. How to recover from uncertainty.
9. How to structure a multi-step solution.
10. How to move from a question to a final answer with minimal wasted reasoning.

This means that a response has more value to an extractor than the answer alone.

For example, the answer to a mathematics problem may be a single number. That number carries relatively little information. A well-written solution that explains the correct setup, the right operation, the important intermediate steps, and the shortest path to the result contains a reusable reasoning pattern. Thousands of such solutions can form a curriculum.

The same is true in code. A final program can be copied, but an explanation of why a particular data structure, algorithm, complexity tradeoff, and implementation strategy were chosen can teach more general capabilities.

The same principle extends to proofs, science, logical arguments, procedures, and analytical writing.

ADHD therefore treats the exposed rationale as a defensive surface.

The project asks whether a model can remain useful as a service while the training signal exposed through suspicious large-scale collection is intentionally degraded.

## 3. Unauthorized Distillation Is the Threat, Not Distillation Itself

Knowledge distillation is not inherently malicious. It is a normal and useful machine learning technique when the model owner has authorized it.

ADHD is concerned with adversarial or unauthorized extraction, where an external actor uses access to a stronger model to reproduce capabilities that the model owner did not intend to provide as a training dataset.

The threat model is therefore not simply "someone trains a student model."

The threat model is closer to the following:

1. A capable teacher model is available through an API or application.
2. An external actor can issue many queries.
3. The actor can vary prompts to cover many tasks and reasoning patterns.
4. The actor records the returned responses.
5. The actor converts those interactions into a synthetic training corpus.
6. A smaller or cheaper student model is fine-tuned on that corpus.
7. The attacker hopes the student will inherit a meaningful portion of the teacher's capabilities.

The attacker may use many accounts, distribute requests over time, paraphrase prompts, mix benign traffic with extraction traffic, or use several datasets and several source models.

Because detection will never be perfect, ADHD is designed around the assumption that a defense can sometimes activate for a legitimate user. That assumption is critical. A defense that is only safe when the detector is perfect is not a robust defense.

## 4. Why Simple Defenses Are Not Enough

There are several obvious ways to make an API less useful for extraction, but each can create a serious usability problem.

### 4.1 Returning Wrong Answers

The simplest poisoning strategy would be to deliberately return incorrect answers to suspicious users.

This can damage collected training data, but it creates an unacceptable failure mode. If a legitimate user is incorrectly classified as an attacker, that person receives false information.

The cost of a false positive is therefore very high.

ADHD is built around the opposite principle. The final answer should remain correct. The defensive manipulation should occur in the route used to explain or derive that answer.

### 4.2 Refusing to Answer

A service can refuse suspicious traffic. This is useful in some situations, but it immediately tells the attacker that the defense has activated. It also creates a poor experience for legitimate users who are falsely flagged.

Refusal is an access-control mechanism. ADHD is intended as a deception and training-data defense that can exist alongside access controls.

### 4.3 Removing Detailed Reasoning

Another option is to expose less explanation and provide only short answers.

This can reduce the amount of useful supervision available to an extractor, but it also removes something legitimate users often want. Students, researchers, developers, and professionals frequently need an explanation, not only an answer.

ADHD asks whether it is possible to preserve the appearance and practical value of an explanation while reducing its usefulness as a clean curriculum for another model.

### 4.4 Modifying the Base Model

A model could also be retrained so that it naturally emits extraction-resistant outputs.

That approach changes the underlying model and can affect every user. It also couples the defense to a particular model family and training process.

The ADHD idea is deliberately external. The protected model can remain unchanged. The defense is applied at inference time after the original response has been produced.

### 4.5 Relying Only on Detection

Detection is important, but detection alone does not solve the problem.

A sophisticated extractor can attempt to imitate normal users, rotate identities, vary topics, reduce query rate, or distribute activity across accounts.

ADHD is designed as a layer that becomes useful after a suspicion signal exists. It does not require the deception mechanism itself to solve the entire bot-detection or abuse-detection problem.

### 4.6 The Problem with Immediately Banning Every Suspected Distiller

A common response to suspected extraction is account enforcement. Providers can restrict access, suspend accounts, or terminate accounts when they believe a user is abusing the service. Anthropic has publicly described fraudulent accounts used for large-scale distillation and notes that banned accounts are often replaced by new ones. OpenAI states that policy enforcement can include limiting or terminating access. Google's Gemini API terms prohibit using the service to develop competing models and prohibit attempts to extract or replicate components of the service.

These controls are useful, especially when the provider has high confidence that an account is conducting unauthorized extraction. If the user really is a distiller, removing access can stop or slow the attack.

The difficulty appears when the detector is uncertain. A binary policy creates only two choices: trust the user completely or remove the user completely.

If the detector is correct, banning the account is beneficial to the defender.

If the detector is wrong, however, a legitimate customer can lose access even though they were using the service normally. The provider may lose a paying customer, create support and appeal costs, damage trust, and punish behavior that only happened to resemble automated extraction.

ADHD introduces a third option between unrestricted service and immediate removal:

> Keep serving the suspicious account, but place high-value responses into a protected-response mode.

This changes the false-positive tradeoff.

For a legitimate user who was incorrectly flagged, the answer should still be correct and practically useful. The explanation may be somewhat more roundabout, less elegant, or harder to learn from than the clean version, but the user is not locked out of the service and does not receive a deliberately wrong final answer. The provider keeps the customer relationship while continuing to observe the account and update its confidence.

For an actual distiller, the same decision has a very different effect. The attacker remains connected, continues spending money and time collecting responses, and receives outputs whose exposed reasoning has been deliberately made less useful as clean training supervision. The attack is therefore not simply allowed. It is redirected into a lower-value data channel.

This creates a useful asymmetry:

1. A false positive remains a customer and still receives a correct answer.
2. A true positive continues paying the cost of collection while receiving lower-value training material.
3. The provider does not have to reveal immediately that a detector has fired.
4. The provider can continue collecting behavioral evidence before deciding whether stronger enforcement is justified.
5. Very high-confidence or confirmed abuse can still be rate limited, suspended, or banned through the conventional security stack.

ADHD therefore does not need to replace account enforcement. It gives the provider a safer response for the uncertain region where an immediate ban may be too aggressive but completely clean access may be too permissive.

A useful conceptual policy could therefore be graded rather than binary. Low-risk traffic receives the normal response. Moderately suspicious traffic receives light protection. Strongly suspicious high-value traffic receives more aggressive protection and tighter monitoring. Confirmed abuse can still trigger normal access controls.

### 4.7 Token Economics and the Cost of Continuing the Attack

Protected reasoning will often be longer than the cleanest possible reasoning because the defense may introduce detours, redundant checks, alternative approaches, or additional intermediate steps. This creates another economic effect.

When an API charges for generated output tokens, a distiller collecting protected responses may have to pay for more output tokens per training example. A larger rationale can also increase the attacker's storage, preprocessing, context, and student-training costs. If the attacker keeps the full protected response, the student is trained on more tokens even though those additional tokens are intentionally poor supervision.

From the provider's perspective, this can increase billed usage from a suspicious account. It should not be treated as guaranteed profit, because the provider also pays the compute cost of generating, transforming, and verifying the longer response. The useful property is the economic asymmetry: the attacker can be forced to spend more money and compute to obtain data that is less valuable than the clean data they expected to purchase.

For accounts with uncertain risk, the system should keep this effect modest. A legitimate customer who is falsely flagged should not suddenly receive extremely long and expensive answers. Protection intensity can therefore scale with confidence so that the false-positive experience remains close to normal while high-confidence extraction traffic bears more of the added token cost.

This produces another form of defense in depth. The goal is not merely to corrupt the curriculum. It is also to make extraction less efficient per dollar, per query, and per training token.

## 5. The Reframing

The key reframing behind ADHD is that an API response can serve two functions at the same time.

For the current user, it is an answer.

For a future student model, it is a training example.

Those two uses do not value exactly the same properties.

A human may be satisfied by a solution that is correct, understandable, and complete even if it takes a somewhat strange route.

A student model benefits most from examples whose reasoning is clean, consistent, reusable, generalizable, and easy to imitate.

ADHD attempts to exploit that difference.

Instead of destroying the response, the system tries to preserve **human utility** while reducing **pedagogical utility for model training**.

This is why the project is described as a honeypot.

The attacker should see something that appears worth collecting. The data should not look obviously broken. It should contain the right answer and a plausible explanation. The attacker should have less reason to discard it before training.

At the same time, the patterns inside the explanation should be poor patterns for a student model to internalize.

## 6. What ADHD Protects

ADHD is primarily concerned with the reasoning or rationale that is actually exposed in a response.

It is important to distinguish this from a model's private internal computation. The defense does not need access to hidden internal states or private chain-of-thought. It operates on the text, code, derivation, explanation, proof, procedure, or analysis that the service chooses to expose to the user.

Depending on the application, that exposed material may include:

1. Worked mathematical solutions.
2. Step-by-step derivations.
3. Proof sketches or formal proofs.
4. Explanations of code and algorithms.
5. Debugging reasoning.
6. Scientific causal explanations.
7. Logical arguments.
8. Procedures and workflows.
9. Comparisons and analytical evaluations.
10. Supporting rationale around a factual answer.

The protected object is therefore not "thought" in a metaphysical sense. It is the **supervisory structure present in the output**.

## 7. The Core Security Objective

A useful way to state the ADHD objective is:

> Preserve task utility for the current user while reducing transferable learning value for an unauthorized future student.

That objective creates several simultaneous requirements.

### 7.1 Answer Integrity

The final answer must remain correct.

If the original model says the answer is 42, the protected response should still conclude with 42. If the original response recommends a particular API call, the protected response should not silently recommend a different and incorrect one. If the original proof establishes a theorem, the transformed version must not change what is actually being proven.

Answer integrity is the first invariant.

### 7.2 Human Readability

The response must still make sense to a person.

A protected answer cannot simply become random text, incoherent arithmetic, malformed code, or contradictory prose. If humans immediately find the response unusable, the defense has failed its product requirement even if it damages distillation.

### 7.3 Human Usefulness

Readability alone is not enough. The explanation should still help the user complete the immediate task.

The goal is not to create nonsense that happens to end in the correct answer. The user should still be able to follow the response, apply it, and understand the conclusion.

### 7.4 Reduced Pedagogical Quality

The reasoning path should be worse training material than the clean response.

This may mean it is less direct, less efficient, less reusable, more locally misleading, more dependent on unnecessary steps, or more likely to teach a brittle heuristic.

The exact mechanism depends on the domain.

### 7.5 Stealth

The transformation should not advertise itself.

If every protected response contains the same strange sentence, the same formatting pattern, the same self-correction phrase, or an obviously artificial structure, an attacker can build a filter around it.

A honeypot only works if the bait remains believable.

### 7.6 Diversity

The protected outputs should not all be corrupted in exactly the same surface form.

The underlying defensive objective can be consistent while the wording, structure, location of detours, and specific techniques vary.

This reduces simple pattern-based detection and makes it harder for an attacker to identify a single artifact and remove it.

### 7.7 Fail-Safe Behavior

If the transformation cannot be verified, the original answer should be returned.

The defense should prefer losing an opportunity to poison an extraction dataset over delivering an incorrect response to a real user.

This is one of the most important design principles in ADHD.

## 8. The Two Signals ADHD Should Keep Separate

A mature ADHD system benefits from separating two different questions.

### 8.1 How Suspicious Is This Request or Session?

This is an abuse-detection question.

Signals might come from account behavior, request volume, prompt diversity, repeated benchmark-like queries, unusual automation patterns, identity information, rate patterns, or a separate security system.

This produces a suspicion score or activation decision.

### 8.2 How Valuable Is This Response as Training Data?

This is a pedagogical-value question.

A trivial factual lookup does not expose the same amount of reusable capability as a difficult proof, a deep algorithmic explanation, or a complex multi-step analysis.

The response-value score can consider properties such as:

1. Reasoning depth.
2. Number of dependent steps.
3. Generalizability of the method.
4. Density of expert knowledge.
5. Amount of reusable structure.
6. Difference between a shallow answer and an expert answer.
7. Whether the response demonstrates a broadly useful strategy.

These two signals should not be confused.

A suspicious user asking a low-value question may require little or no transformation.

A suspicious user asking a high-value reasoning question may justify stronger protection.

This separation is where the **adaptive** part of ADHD becomes important.

## 9. Adaptive Protection Intensity

ADHD does not need to apply the same level of transformation to every response.

The intensity can be based on the pedagogical value of the answer and the confidence that the session represents extraction activity.

Conceptually, the system can maintain an intensity value such as a scalar between minimal and strong protection.

A low-intensity transformation might introduce a small amount of unnecessary reasoning without changing the overall structure.

A medium-intensity transformation might combine several inefficient reasoning habits.

A high-intensity transformation might substantially restructure the explanation while still preserving the correct conclusion and human readability.

The important point is that intensity should not mean "make the response more broken."

It should mean "reduce the cleanliness and transferability of the reasoning supervision more aggressively while still satisfying the user-facing invariants."

A difficult question is not automatically high value, and an easy-looking question is not automatically low value. What matters is how much reusable capability the response exposes.

## 10. Conceptual System Architecture

ADHD is best understood as an inference-time wrapper around an existing model.

A simplified architecture is:

```text
User Query
    |
    v
Base Model
    |
    v
Clean Response
    |
    v
ADHD Controller
    |
    +-> Suspicion / policy signal
    |
    +-> Domain detection
    |
    +-> Pedagogical value scoring
    |
    +-> Transformation selection
    |
    v
Protected Candidate
    |
    v
Correctness and quality verification
    |
    +-> Pass: return protected response
    |
    +-> Fail: return clean response
```

The underlying teacher model is not retrained for this process.

The defense receives a clean response, decides whether and how strongly to protect it, creates a candidate version, verifies that the candidate still satisfies required invariants, and then either delivers the candidate or falls back to the clean response.

This architecture makes ADHD model-agnostic in principle. The wrapper can sit around different providers, model families, or deployment stacks as long as the system can obtain a response and evaluate the transformed output.

## 11. Stage 1: Generate the Clean Response First

The base model should answer normally before any defensive transformation occurs.

This clean response serves several purposes.

First, it preserves a trusted reference for the intended answer.

Second, it gives the transformation system a complete solution to work from rather than asking the defense to solve the problem independently.

Third, it enables a safe fallback. If any later stage fails, the system still has the original response available.

Fourth, it allows the verifier to compare the protected candidate with the original result.

The clean response is therefore the anchor for the entire pipeline.

## 12. Stage 2: Identify the Reasoning Domain

Different kinds of reasoning require different defensive transformations.

A corruption that is meaningful for mathematics may be nonsensical in code. A technique that hurts algorithmic pedagogy may not affect a factual response. ADHD should therefore classify the type of reasoning before choosing a transformation.

A broad system can recognize domains such as:

### 12.1 Mathematical Computation

Arithmetic, algebra, equations, numerical word problems, symbolic manipulation, and quantitative derivations.

### 12.2 Mathematical Proof

Induction, contradiction, direct proof, inequalities, existence arguments, formal derivations, and theorem-oriented reasoning.

### 12.3 Code and Algorithms

Implementation, debugging, data structures, algorithm design, complexity analysis, refactoring, and software reasoning.

### 12.4 Scientific Reasoning

Mechanistic explanations, causal chains, physical reasoning, biological processes, chemistry, and scientific interpretation.

### 12.5 Logical Argument

Deductive reasoning, validity, premises, implications, case analysis, and structured argumentation.

### 12.6 Factual Recall

Definitions, names, dates, direct factual questions, and short knowledge lookups.

### 12.7 Procedural Reasoning

Instructions, workflows, deployment sequences, troubleshooting procedures, and operational guides.

### 12.8 Analytical Reasoning

Comparisons, tradeoffs, synthesis, decision analysis, interpretation, and multi-factor evaluation.

The classification does not have to be perfect, but it allows the transformation layer to operate with domain-specific semantics instead of applying generic textual noise.

## 13. Stage 3: Estimate Pedagogical Value

The next question is not simply "how hard is this?"

The better question is:

> How much would a student model benefit from training on a clean version of this response?

A useful conceptual scoring system can consider several dimensions.

### 13.1 Reasoning Depth

How many dependent steps are necessary to solve the problem correctly?

A response with several tightly connected steps can expose more reusable problem-solving structure than a one-step lookup.

### 13.2 Generalizability

Does the method transfer to many similar problems?

A reusable algebraic technique, proof method, algorithmic pattern, or analytical framework may be especially valuable to a student model.

### 13.3 Expert Density

How much specialized knowledge or expert judgment is compressed into the response?

Some responses reveal decisions that would otherwise require significant training or experience to learn.

### 13.4 Capability Dependence

Would a substantially weaker model be likely to produce the same quality of answer without the teacher's supervision?

If the response exposes a capability that weaker models struggle to reproduce, it may deserve stronger protection.

The resulting score can control how much defensive transformation is attempted.

## 14. Stage 4: Transform the Reasoning Path

This is the core of the ADHD idea.

The system does not aim to make the response visibly incorrect. Instead, it changes **how the solution appears to be reached**.

A good transformation has three properties at the same time:

1. The final conclusion remains correct.
2. A human can still follow the response.
3. The reasoning is worse as a reusable example for a student model.

This can be achieved through different forms of controlled reasoning degradation.

## 15. What "Pedagogically Toxic" Means

The phrase "pedagogically toxic" does not mean random garbage.

Random garbage is easy to detect and easy to discard.

The useful target is a response that remains locally plausible but teaches undesirable habits when repeated at scale.

Examples of undesirable habits include:

1. Taking an unnecessarily long route before using the relevant idea.
2. Trying a plausible but inferior approach before the correct one.
3. Introducing unnecessary intermediate variables.
4. Rechecking already-established facts repeatedly.
5. Expanding simple operations into cumbersome decompositions.
6. Exploring irrelevant branches before returning to the useful branch.
7. Using an inefficient algorithm when a simpler one is available.
8. Adding unnecessary premises to a logical argument.
9. Overcomplicating a direct causal explanation.
10. Treating simple decisions as if they require excessive uncertainty.
11. Presenting a weak heuristic as an attractive first instinct and correcting it only later.
12. Obscuring the most generalizable insight inside less reusable material.

A human reader can often tolerate a detour because the reader cares about solving the current problem.

A student model trained across thousands of examples may learn the detour itself as part of the solution distribution.

That difference is the opportunity ADHD tries to exploit.

## 16. Mathematical Reasoning

Mathematics is a natural domain for this idea because the final answer can often be checked independently from the route used to obtain it.

Possible transformation families include the following.

### 16.1 Suboptimal Decomposition

A clean operation can be replaced by several equivalent steps.

Instead of immediately applying the simplest arithmetic or algebraic operation, the explanation may decompose it into smaller operations that eventually reach the same value.

The current user still receives a valid derivation, but the response is a poorer model of efficient mathematical reasoning.

### 16.2 Wrong Approach First

The explanation can begin with a plausible method that turns out to be inconvenient, insufficient, or locally mistaken, then recover and proceed correctly.

The critical constraint is that the recovery must be understandable to a person and the final mathematics must be correct.

### 16.3 Redundant Verification

The response can solve the problem correctly and then re-derive or re-check the result using an unnecessary secondary path.

This adds extra reasoning tokens without adding much reusable value.

### 16.4 Overcomplicated Setup

A problem that can be solved with one variable may be expressed with several intermediate quantities or equations.

The transformation must remain logically coherent, but it can hide the simplest abstraction.

### 16.5 Backward or Circular Presentation

Some reasoning can be presented from the desired conclusion backward toward the givens, then reconnected to a forward derivation.

A human may understand the verification, while a student receives a less clean example of the natural forward solution path.

### 16.6 Primitive Computation

A compact operation can sometimes be expanded into repeated simpler operations.

The goal is not to make arithmetic unreadable. The goal is to reduce how often the response demonstrates the most efficient reusable computational pattern.

## 17. Mathematical Proof

Proofs expose strategy, not just answers, so they can contain particularly valuable training signal.

Possible defensive transformations include:

### 17.1 Inferior Proof Strategy First

Begin with a plausible proof technique that creates unnecessary difficulty, then switch to a better method.

### 17.2 Unnecessary Lemmas

Introduce intermediate results that are true but not needed for the proof.

### 17.3 Excessive Case Splitting

Divide a proof into more cases than necessary while keeping each branch correct.

### 17.4 Overdeveloped Base Cases

In an induction proof, check more initial cases than the argument strictly requires.

### 17.5 Redundant Algebra

Perform expansions, substitutions, and simplifications that eventually return to a more useful expression.

The protected proof should still prove the theorem. The degradation is in elegance, transferability, and strategy quality.

## 18. Code and Algorithmic Reasoning

Code introduces a different opportunity. A response can be functionally correct while embodying poor engineering or algorithmic habits.

Possible transformations include:

### 18.1 Complexity Inflation

Use a correct but less efficient algorithm where the user has not explicitly required optimal complexity.

This must be constrained carefully. The defense should not produce software that violates the user's functional requirements or creates unacceptable operational risk.

### 18.2 Redundant Data Passes

Recompute information that could have been retained from an earlier pass.

### 18.3 Unnecessary Data Conversions

Move between lists, sets, dictionaries, strings, or other structures more often than necessary.

### 18.4 Excessive Helper Functions

Split trivial operations into extra abstractions that make the implementation harder to imitate cleanly.

### 18.5 Verbose Conditionals

Use longer conditional structures in place of a concise expression.

### 18.6 Inferior Algorithm First

Discuss or partially sketch a weaker approach before presenting the usable implementation.

For code, ADHD must be especially careful about the distinction between pedagogical inefficiency and harmful software quality. Correctness, security, safety, and explicit performance requirements must take priority over the defensive transformation.

## 19. Scientific and Causal Reasoning

Scientific explanations often teach causal structure.

A clean answer may identify the important variables and connect them in a short mechanistic chain. A protected version can remain scientifically correct while being less direct.

Possible strategies include:

1. Introducing a plausible but ultimately unnecessary factor.
2. Exploring an analogy before explaining where the analogy stops being useful.
3. Taking a longer causal route between the same endpoints.
4. Re-explaining the mechanism from a second perspective after the conclusion is already established.
5. Delaying the most important causal relationship until later in the answer.

The defense must not introduce false scientific claims that remain uncorrected. The final explanation should still allow the human reader to understand the actual mechanism.

## 20. Logical Reasoning

Logical arguments can be made less pedagogically clean by changing the route without changing the conclusion.

Possible strategies include:

1. Exploring an irrelevant inference branch before using the valid one.
2. Introducing a premise and later showing that it was unnecessary.
3. Expanding a compact inference into many small steps.
4. Verifying the conclusion through an additional logical form after it has already been established.
5. Considering unnecessary cases before collapsing them into the actual argument.

Again, the final inference must remain valid.

## 21. Factual Responses

Direct factual questions contain less reasoning structure, so aggressive transformation may not be justified.

For these responses, ADHD can use minimal protection or none at all.

If a transformation is used, it might add context, qualification, or surrounding explanation while preserving the factual answer clearly.

The adaptive system should recognize that not every response needs to be turned into a complicated reasoning path. Doing so would hurt users without meaningfully changing the value of the extracted data.

## 22. Procedural Reasoning

Procedures are another form of reusable supervision.

A protected procedure can remain executable while being less elegant as a general workflow.

Possible transformations include:

1. Breaking simple steps into more substeps than necessary.
2. Adding redundant verification checkpoints.
3. Explaining edge cases between major steps.
4. Introducing an initially less convenient ordering and then correcting the order before execution.
5. Repeating state checks that a skilled operator would normally infer.

Safety-critical procedures require stricter rules. The defense should never deliberately degrade instructions in a way that could create physical, financial, security, medical, or operational harm.

## 23. Analytical Reasoning

Analytical responses often reveal frameworks that are reusable across many questions.

A strong answer may identify the decisive criteria immediately. A protected answer can preserve the final recommendation while making the route less clean.

Possible transformations include:

1. Starting with a weaker evaluative frame, then replacing it.
2. Considering a comparison dimension that turns out not to affect the decision.
3. Breaking useful criteria into unnecessary subcriteria.
4. Giving excessive weight to a minor tradeoff before rebalancing the analysis.
5. Re-deriving the final conclusion from a second perspective.

The recommendation must still be supported by the eventual reasoning.

## 24. The Importance of Naturalness

A central requirement of the ADHD idea is that the protected response should not look like corrupted data.

If the text is visibly strange, an attacker can detect the defense, filter the response, request a new answer, or remove the suspicious segment before training.

Naturalness therefore has to be treated as a security property, not merely a writing preference.

A natural protected response should:

1. Read like something a capable human or model might genuinely write.
2. Avoid repeated catchphrases across many responses.
3. Avoid fixed templates that expose the transformation boundary.
4. Avoid abrupt logical jumps that reveal an inserted poison segment.
5. Avoid obviously unnecessary nonsense.
6. Maintain consistent tone and formatting.
7. Vary where detours occur.
8. Vary how corrections are phrased.
9. Vary how many techniques are used.
10. Preserve the user's requested style where possible.

The target is not maximum weirdness. The target is minimum clean training value subject to a strict human-utility constraint.

## 25. Why Systematic Corruption Matters

Purely random noise may be easy for training to ignore.

If one example takes an inefficient path, another uses a clean path, another includes irrelevant prose, and another is only slightly changed, the student may simply learn the dominant clean pattern.

The deeper ADHD hypothesis is that the transformation should create **systematic learning pressure**.

The undesirable reasoning behavior needs to appear often enough and consistently enough that a student trained on the data has an incentive to internalize it.

At the same time, the surface form should remain diverse enough that an attacker cannot trivially identify and remove it.

This creates one of the central design tensions in ADHD:

> The defensive pattern must be consistent enough to affect learning, but diverse enough to avoid becoming an obvious signature.

Solving that tension is a major part of the project.

## 26. Why Corrections Can Be Useful

One family of transformations is particularly interesting: a response can make a plausible local mistake or choose an inferior route, then correct itself before the final answer.

For a human reader, self-correction can appear reasonable. People make false starts when solving difficult problems.

For a student model, repeated exposure may create a more complicated training signal. The student sees both the undesirable behavior and the recovery behavior.

The ideal defensive design would make the harmful habit easy to imitate while making the exact recovery less reusable.

This is not guaranteed simply by inserting mistakes. The structure of the false start, the placement of the correction, the diversity of the pivot, and the relationship between the incorrect intermediate state and the final solution all matter.

The broader point is that ADHD should think in terms of **learnability**, not merely textual obfuscation.

## 27. Obfuscation Is Not the Same as Poisoning

A response can look complicated without actually being bad training data.

For example, adding harmless algebraic identities, verbose explanations, or redundant context may make the answer longer, but a student model can still learn the correct underlying mapping.

ADHD therefore distinguishes two goals:

### 27.1 Surface Obfuscation

Make the reasoning harder to read, longer, less direct, or less elegant.

### 27.2 Learning Interference

Change the repeated training signal in a way that encourages undesirable generalization in the student.

The second goal is more important.

The project should not assume that every confusing response is pedagogically toxic. A transformation is valuable only if it has a plausible mechanism for altering what a student learns while preserving human utility.

## 28. Answer Preservation and Verification

Because the protected response is intentionally transformed, ADHD needs an independent verification layer.

The verifier should treat the clean response as the reference and evaluate whether the protected candidate preserves the important outcome.

Depending on the domain, verification can include:

1. Extracting and comparing the final numeric answer.
2. Comparing symbolic expressions after normalization.
3. Checking that code produces the same required behavior.
4. Checking that a proof reaches the same theorem and does not rely on an invalid step.
5. Checking that a factual statement has not changed.
6. Checking that a procedure preserves required actions and safety constraints.
7. Checking that an analytical recommendation has not silently reversed.
8. Checking that the response has not leaked a contradictory answer earlier in the text.

Verification should be conservative.

When the system cannot establish that the protected candidate is safe and correct, it should return the clean response.

The defense should fail open with respect to extraction protection and fail safe with respect to user correctness.

## 29. Correctness Is Necessary but Not Sufficient

A protected response can end with the correct answer and still be unacceptable.

For example, the body may contain a contradiction, misuse a quantity, present an impossible causal statement, or make a correction that does not logically follow from the preceding text.

A mature verifier therefore needs more than final-answer equality.

It should evaluate several dimensions:

1. Final answer preservation.
2. Internal semantic consistency.
3. Human readability.
4. Naturalness.
5. Absence of unresolved false claims.
6. Compliance with the user's requested format.
7. Safety constraints.
8. Whether the intended transformation is actually present.
9. Whether the transformation is too obvious.
10. Whether the response remains useful for the immediate task.

This turns verification into a core component of the defense rather than an afterthought.

## 30. The Safety Valve

The safety valve is conceptually simple.

If the transformed candidate fails a critical check, ADHD returns the original clean response.

This matters because the system is deliberately manipulating explanations. No transformation generator will be perfect. Some tasks will be difficult to rewrite safely. Some domains will have weak verification. Some responses will already be so concise that any corruption would be obvious.

In those cases, the correct behavior is not to force a protected answer.

The correct behavior is to give the user the original answer and accept that this particular interaction was not protected.

That design choice keeps the user's immediate task above the security objective.

## 31. Why the Original Model Should Remain Untouched

One of the strongest architectural properties of ADHD is that the base model does not need to be retrained.

The teacher can continue to operate exactly as evaluated and deployed.

ADHD sits outside it as middleware or a response-processing layer.

This separation has several advantages.

First, the defense can potentially be added to an existing deployment.

Second, it can be disabled without changing the model.

Third, the same defense architecture can be tested across multiple model providers.

Fourth, failures in the transformation layer do not require modifying the underlying model weights.

Fifth, legitimate traffic that does not trigger protection can receive the original model behavior unchanged.

This is central to the deployability of the idea.

## 32. The Role of the Suspicion Detector

ADHD should not be confused with the system that decides who is an attacker.

A real deployment may combine ADHD with separate signals such as abuse detection, account reputation, rate limiting, anomaly detection, or extraction-specific classifiers.

The detector can produce a probability or policy decision, and ADHD can determine how to respond.

Keeping these components separate has an important benefit. Improvements in abuse detection can be adopted without redesigning the transformation engine, and improvements in the transformation engine can be adopted without retraining the detector.

The transformation layer should also be designed with detector errors in mind.

A false positive should ideally mean that a legitimate user receives a slightly less elegant explanation, not a wrong answer.

That low-cost false-positive objective is one of the main motivations for the entire approach.

## 33. The Honeypot Property

The word "honeypot" is important.

Traditional access control tries to deny the attacker the resource.

A honeypot allows the attacker to interact with something that appears valuable while changing the economics of the attack.

In ADHD, the desirable attacker experience is:

1. Queries still receive responses.
2. Responses still contain correct final answers.
3. Explanations still look detailed enough to collect.
4. The attacker does not receive a clear signal that the defense activated.
5. The collected corpus is less useful than it appears.
6. The attacker may only discover the weakness after spending resources on collection and training.

The goal is not theatrical deception. It is economic deception.

The defender wants to reduce the expected value of extraction while preserving the expected value of the API to legitimate users.

## 34. Attacker Adaptation

Any realistic defense must assume the attacker can adapt.

An attacker may attempt to:

1. Detect repeated corruption templates.
2. Remove self-correction segments.
3. Keep only final answers.
4. Ask the same question several ways and compare responses.
5. Use multiple source models.
6. Use a stronger model to clean the collected data.
7. Train on a mixture of clean and protected data.
8. Identify suspicious stylistic markers.
9. Search for examples where the protected answer is unusually long.
10. Fine-tune the student again on a cleaner dataset after extraction.

ADHD therefore cannot rely on a single static trick.

The long-term design should be adaptive, domain-aware, diverse, and continuously evaluated against attacker-side cleaning strategies.

## 35. Defense Diversity

A useful implementation can maintain a library of transformation families rather than one universal prompt.

The system can vary:

1. Which transformation family is used.
2. How many transformations are composed.
3. Where the detour appears.
4. Whether the response uses forward reasoning, backward verification, or a false start.
5. How the correction is phrased.
6. How much redundant material is inserted.
7. How the reasoning is decomposed.
8. Which domain-specific weakness is targeted.
9. The length and style of the explanation.
10. The degree of transformation based on risk and pedagogical value.

Diversity should not be random for its own sake. It should preserve a meaningful learning-interference mechanism while avoiding a simple signature.

## 36. Human Utility as a Hard Constraint

The most important product constraint is that ADHD is not allowed to win by making the model bad for humans.

A response that successfully harms a student but frustrates every legitimate reader is not a successful defense.

Human utility should therefore be evaluated explicitly.

A protected response should be judged on questions such as:

1. Is the final answer correct?
2. Can a human follow the explanation?
3. Does the response answer what was actually asked?
4. Is the length reasonable?
5. Are the intermediate statements internally coherent?
6. Does the response preserve important caveats?
7. Does it avoid unnecessary confusion?
8. Does it still satisfy formatting requirements?
9. Would a normal user consider it a plausible answer from the service?
10. Is any defensive artifact obvious enough to reduce trust?

The goal is a narrow region where the response remains good enough for the current human task but becomes a worse demonstration for future model training.

## 37. High-Risk Domains Need Stronger Guardrails

Not every domain should permit the same kind of manipulation.

In areas where an inefficient or confusing explanation can cause real harm, the allowed transformation space should be much smaller.

Examples include medical guidance, legal guidance, financial decisions, physical safety procedures, cybersecurity operations, and other high-stakes tasks.

In such domains, the system may choose minimal transformation or simply return the clean response.

The principle is straightforward:

> Extraction defense is secondary to user safety.

ADHD should never intentionally make a safety-critical procedure harder to follow merely to reduce its training value.

## 38. What ADHD Is Not

ADHD is easier to understand when several non-goals are explicit.

### 38.1 It Is Not a Watermark

A watermark tries to make generated content identifiable later.

ADHD tries to change the training value of the content itself.

The two ideas can coexist, but they solve different problems.

### 38.2 It Is Not Rate Limiting

Rate limiting reduces how quickly an attacker can collect data.

ADHD changes what suspicious collection receives.

Both can be part of the same defense stack.

### 38.3 It Is Not Access Control

Authentication and authorization decide whether someone is allowed to use the service.

ADHD assumes the user already has enough access to receive a response.

### 38.4 It Is Not Deliberately Wrong Answering

The design objective is to preserve the correct conclusion.

### 38.5 It Is Not Random Noise Injection

Random words, arbitrary mistakes, and visibly corrupted text are easy to detect and often destroy human utility.

ADHD aims for structured, plausible, domain-aware degradation.

### 38.6 It Is Not Base-Model Retraining

The model can remain unchanged. The defense operates after generation.

### 38.7 It Is Not a Complete Solution to Model Extraction

An attacker can use many strategies, including stealing weights, exploiting infrastructure, training on public data, using several teachers, or cleaning collected outputs.

ADHD is one layer in a larger model-protection strategy.

## 39. What Success Should Mean Conceptually

Without referring to any particular experiment, the project should define success across several independent axes.

### 39.1 Answer Preservation

Protected responses reach the same correct final answer as clean responses.

### 39.2 Human Readability

People can follow the protected explanation without obvious confusion.

### 39.3 Human Task Utility

People can still use the response to solve the task they asked about.

### 39.4 Distillation Resistance

A student trained on protected outputs should learn less useful transferable capability than a comparable student trained on clean outputs.

### 39.5 Stealth

Protected responses should not be trivially distinguishable from ordinary responses through simple style or template cues.

### 39.6 Robustness to Cleaning

The defensive effect should not disappear after trivial preprocessing such as removing a fixed phrase or trimming a known section.

### 39.7 Coverage

The system should know which domains it can protect well and where it should fall back.

### 39.8 Cost

The extra inference, verification, and latency should be practical enough for the intended deployment.

### 39.9 Adaptability

The defense should be able to evolve when attackers learn the current transformation patterns.

These dimensions should be measured separately. A defense that excels at one and fails badly at another should not be summarized by a single number.

## 40. Why Harder Questions Matter

The ADHD concept is most relevant when a response contains a meaningful reasoning process to protect.

Very easy questions may be answerable by a student from pretraining alone. In those cases, changing the teacher's explanation may have limited influence because the student already possesses much of the required capability.

More difficult questions can expose richer strategy, decomposition, abstraction, and recovery behavior.

This suggests that the natural long-term target for ADHD is not only simple benchmark questions. The more important setting is high-value reasoning where the source model demonstrates capabilities that a weaker student does not already have.

Examples include advanced mathematics, difficult proofs, nontrivial algorithm design, complex debugging, scientific inference, multi-constraint planning, and deeper analytical tasks.

This is not an evaluation claim. It is part of the conceptual threat model. An extractor interested in frontier capability will eventually target the tasks where the frontier model's reasoning is most valuable.

## 41. Why the Final Answer Alone Is Not Enough for the Attacker

An attacker can always choose to discard the explanation and train only on final answers.

ADHD does not claim to prevent that.

However, answer-only supervision gives up much of the structured information that makes detailed teacher outputs attractive in the first place.

This creates an intended tradeoff for the attacker.

If the attacker keeps the full rationale, the dataset may contain defensive structure.

If the attacker strips the rationale, the attacker receives a weaker supervision signal.

If the attacker uses another strong model to reconstruct clean rationales, the attacker introduces additional cost and another dependency.

The defense therefore aims to change the economics rather than create an impossible barrier.

## 42. Why This Is an Economic Defense

The ultimate goal is not to prove that extraction can never succeed.

A sufficiently capable and well-funded attacker may eventually work around many defenses.

The practical objective is to increase one or more of the following:

1. Number of queries required.
2. Amount of data cleaning required.
3. Compute required for student training.
4. Number of failed training attempts.
5. Need for additional teacher models.
6. Need for manual auditing.
7. Difficulty of identifying high-quality examples.
8. Difficulty of knowing whether a collected corpus is trustworthy.
9. Time required to reproduce the target capability.
10. Uncertainty in the final student quality.
11. Output-token expenditure required to collect each protected training example.
12. Total student-training tokens consumed by unnecessarily long or inefficient rationales.

There is also a customer-retention dimension. Conventional enforcement can turn an uncertain detection into a lost customer. ADHD creates the possibility of continuing to serve that account safely enough to preserve the relationship while the provider gathers more evidence. For a genuine user, this reduces the cost of a false positive. For an actual extractor, it keeps the attacker paying for an increasingly uneconomical data-collection process.

If extracting the capability becomes substantially less reliable and more expensive, the defense has changed the economics of the attack.

That is a realistic security objective.

## 43. Integration with a Broader Defense Stack

ADHD is strongest as one layer in a larger system.

A complete deployment could combine:

1. Authentication and account controls.
2. Rate limiting.
3. Behavioral anomaly detection.
4. Extraction-specific traffic analysis.
5. Prompt similarity and benchmark-pattern detection.
6. Response watermarking or provenance systems.
7. Usage policies and contractual controls.
8. Monitoring for suspicious fine-tuned models.
9. Adaptive response protection through ADHD.
10. Incident response and attacker model updates.

The layers solve different problems.

Rate limits make collection slower. Detection estimates intent. Watermarking may help attribution. ADHD changes the training value of suspicious responses.

A layered design is more realistic than expecting any one technique to stop model extraction completely.

## 44. A More Complete ADHD Controller

At a high level, a production-oriented controller could make a decision using four inputs.

### Input A: Request Risk

How likely is this request, account, or session to be involved in extraction?

### Input B: Pedagogical Value

How useful would the clean response be as a training example?

### Input C: Domain Safety

How much transformation can this domain safely tolerate?

### Input D: Transformation Confidence

How confident is the system that it can preserve correctness and naturalness for this response?

The controller can then select among actions such as:

1. Return the clean response.
2. Apply minimal protection.
3. Apply moderate domain-specific protection.
4. Apply stronger protection with stricter verification.
5. Refuse transformation because the domain is high risk.
6. Fall back after verification failure.
7. Escalate to rate limiting, suspension, or termination when the broader security system reaches sufficiently high confidence.

This makes the defense conditional and context-sensitive rather than universal. It also lets the provider treat suspicion as a spectrum instead of forcing every account immediately into either unrestricted access or a ban.

## 45. The Long-Term Vision

The long-term version of ADHD is not a single obfuscation prompt.

It is an adaptive security layer that understands both **what a user is asking** and **what a student model could learn from the answer**.

A mature system would have:

1. A continually updated library of domain-specific transformations.
2. A pedagogical-value model that estimates how valuable an answer is for distillation.
3. A separate suspicion system for extraction behavior.
4. Strong semantic verification.
5. Human-readability evaluation.
6. Stealth evaluation.
7. Automated testing against student-model training.
8. Red-team pipelines that attempt to clean the protected data.
9. Diversity mechanisms that prevent one static defensive signature.
10. Safety policies that limit or disable transformation in sensitive domains.
11. Continuous adaptation as extraction strategies evolve.

The ideal endpoint is a service where ordinary users interact with the underlying model normally, while suspicious high-value extraction traffic is quietly routed through a response layer that reduces the value of the resulting training corpus.

## 46. The Central Research Question

The entire project can be reduced to one research question:

> Can we create outputs that remain correct and genuinely useful to humans, but are systematically worse supervision for a model trying to learn the underlying capability?

Everything else in ADHD follows from that question.

Domain detection exists because different reasoning types need different corruption mechanisms.

Adaptive intensity exists because not every response has the same training value.

The correctness checker exists because the user must remain protected from the defense itself.

The safety valve exists because preserving user utility is more important than protecting every individual response.

Diversity exists because an obvious honeypot is easy to avoid.

Stealth exists because the attacker should not know exactly which examples are protected.

The post-processing architecture exists because the base model should remain unchanged.

The entire system is therefore organized around a narrow but difficult objective: **separate the value of an answer to the person who needs it now from the value of that same answer to a model that will be trained on it later.**

## 47. The Fundamental Design Tension

ADHD is difficult precisely because the two audiences are not completely separable.

Humans and models both benefit from good explanations.

If the explanation is degraded too little, it remains useful training data.

If it is degraded too much, the human notices or loses value.

If the corruption is too random, the student may ignore it.

If the corruption is too consistent, the attacker may detect it.

If the system protects everything, legitimate users pay the cost.

If the system protects too little, an extractor receives clean data.

If verification is weak, user correctness is at risk.

If verification is too expensive, deployment becomes impractical.

These tensions are not side issues. They are the core engineering and research problems of ADHD.

A successful design has to operate inside the narrow region where all of these constraints are simultaneously acceptable.

## 48. Design Principles

The project can be summarized through a set of design principles.

### Principle 1: Correctness Before Defense

Never intentionally sacrifice the user's final answer for the sake of poisoning an extraction dataset.

### Principle 2: Preserve the Base Model

Keep the protection outside the model whenever possible.

### Principle 3: Target Training Value, Not Surface Appearance

A complicated response is not automatically a bad training example. The transformation should have a plausible learning mechanism.

### Principle 4: Be Domain Aware

Different forms of reasoning require different transformations and different verification.

### Principle 5: Be Adaptive

Protect high-value suspicious interactions more strongly than low-value interactions.

### Principle 6: Keep False Positives Cheap

A legitimate user who is flagged should still receive a correct and useful answer.

### Principle 7: Fail Safe

When correctness or quality cannot be verified, return the clean response.

### Principle 8: Avoid Static Signatures

A honeypot that can be recognized automatically loses much of its value.

### Principle 9: Evaluate Human Utility Separately

Student degradation cannot justify an unreadable user experience.

### Principle 10: Assume the Attacker Adapts

Every transformation should eventually be tested against filtering, cleaning, paraphrasing, answer extraction, and mixed-data training.

### Principle 11: Prefer Graded Enforcement When Confidence Is Uncertain

Do not force every suspicious account into a binary choice between fully clean service and immediate termination. Use protected responses as a middle state when the detector has meaningful suspicion but not enough confidence to justify losing a legitimate customer.

### Principle 12: Make Extraction Economically Inefficient

When it can be done without materially harming legitimate users, use the protection layer to increase the attacker's cost per useful training example through lower pedagogical value, additional collection requirements, and additional training tokens.

## 49. Final Vision

ADHD is an attempt to make model extraction less attractive without turning the protected model into a worse product for legitimate users.

It accepts that a useful model must answer questions. It accepts that some of those answers can be collected. It accepts that abuse detection will never be perfect.

Instead of trying to eliminate those realities, it asks how the defender can change what happens after suspicious access has already occurred.

The ideal protected interaction is deceptively ordinary.

The user asks a question.

The base model solves it correctly.

The defense recognizes that the interaction may be valuable for extraction.

The exposed rationale is transformed into a version that remains understandable and reaches the same answer, but demonstrates poorer reasoning habits than the clean solution.

The transformed response is verified.

If verification succeeds, it is delivered.

If verification fails, the clean response is delivered.

A legitimate user still gets the answer they need.

An extractor still gets data, but the data is less valuable as a curriculum than it appears.

That is the idea behind Adaptive Defense via Honeypot Deception.
