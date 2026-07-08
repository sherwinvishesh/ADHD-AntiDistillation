# Motivation
## Why ADHD Exists and Why It Matters

---

## The Problem

Building a frontier AI model costs hundreds of millions of dollars.
Training data, compute, researcher time, safety work — the
investment is enormous. And yet, someone with a few hundred dollars
and API access can systematically query that model, collect its
responses, and train a competing model on those responses.

This is called **knowledge distillation**, and when done without
permission it is effectively theft at an industrial scale.

In February 2026, Anthropic publicly confirmed that this had
happened to them. Three organizations ran coordinated campaigns
using tens of thousands of fake accounts and millions of API
queries specifically to extract and replicate Claude's capabilities.
One campaign alone ran over thirteen million exchanges. When
Anthropic released a new model, one of the attackers pivoted
to target it within twenty-four hours.

This was not a theoretical concern. It happened. It is happening
right now to every frontier model with a public API.

---

## Why This Is Harder to Stop Than It Sounds

The fundamental difficulty is this: **any model that answers
questions is producing trainable data.**

There is no way to answer a question usefully without producing
an output that someone could, in principle, train another model on.
This is not a loophole that can be patched. It is a mathematical
property of the problem.

This means the question is never "how do we prevent them from
collecting outputs?" The question is "what can we do about it
given that they will collect outputs?"

---

## What Existing Defenses Do Wrong

The research community has tried several approaches. Each one
solves part of the problem while creating a different problem
in its place.

**Returning wrong answers to suspected attackers** is the most
obvious approach. If the attacker collects wrong answers, their
stolen model learns wrong things. The problem is that no detector
is perfect. When you accidentally flag a real user as a suspected
attacker and return a wrong answer, you have failed that user.
A real person asking a real question got incorrect information.
This is not an acceptable tradeoff.

**Removing the reasoning chain entirely** for suspected attackers
has been shown to significantly degrade what a stolen model can
learn. But this approach requires the defense to be active for
all users because sophisticated detectors are hard to build
reliably. When reasoning chains are stripped from everyone,
the original model effectively becomes worse for everyone. One
evaluation found that CoT removal caused the protected model's
own math accuracy to fall from 78% to 12%. The defense hurt the
defender.

**Modifying the model itself** to produce outputs that are harder
to distill requires retraining, adds risk, and permanently changes
the model's behavior. Every user is affected by a change made to
stop attackers. The model that legitimate users interact with is
no longer the model that was carefully trained and evaluated.

Every existing approach shares a common flaw: **the cost of a
false positive is high.** When the defense accidentally triggers
on a real user, something bad happens to that user. This forces
defenders to be conservative, which means attackers get through.

---

## The Insight Behind ADHD

The key insight is a reframing of the problem.

When an attacker queries a model and collects its responses,
they are not just collecting answers. They are collecting the
model's **reasoning process** — the step by step thinking that
encodes how to approach problems, how to structure solutions,
how to generalize from one situation to another.

This reasoning process is what makes frontier models valuable.
A model that has learned *how to think* through problems can
handle novel situations it has never seen. A model that has
only learned to mimic surface patterns cannot.

ADHD targets this specifically. The reasoning process is what
gets corrupted. The answer is left completely intact.

When someone queries an ADHD-protected model, they receive a
response that looks completely normal. The answer is correct.
The explanation is coherent. A human reading it would find
nothing wrong. But the reasoning *path* taken to arrive at
that answer is deliberately inefficient, roundabout, and
pedagogically toxic.

A model trained on thousands of these responses does not learn
how to think. It learns bad thinking habits — habits that look
reasonable on the surface but fail catastrophically when applied
to novel problems. The stolen model answers questions it has
seen before adequately. On anything genuinely new or complex,
it fails.

The honeypot works because the bait looks real. The attacker
collects what appears to be valuable training data. They train
their model. They discover their model does not work properly.
By the time they realize something is wrong, they have already
spent the resources.

---

## Why This Does Not Hurt Real Users

Two properties are maintained without exception.

**The answer is always correct.** Every user, whether they are
a legitimate researcher or an active attacker, always receives
the correct final answer to their question. There are no wrong
answers served to anyone. If something goes wrong in the
corruption process, the original response is returned instead.
The system fails safe.

This means the false positive problem is effectively eliminated.
If the detection system incorrectly flags a real user as a
suspected attacker, that user receives a correct answer with
a slightly roundabout explanation. They got what they needed.
They may not even notice. This is qualitatively different from
every other defense, where a false positive means a real user
gets wrong information.

**The original model is never touched.** The protection layer
sits entirely outside the model. It intercepts responses after
they are generated, conditionally adjusts the reasoning path,
and passes the result along. The model itself runs exactly as
it always has. Its weights are unchanged. Its capabilities are
unchanged. Its behavior for users who are not flagged is
completely unchanged.

This means the protection can be added to any deployed model
without retraining, without risk to model quality, and without
any change to the experience of the vast majority of users who
are interacting legitimately.

---

## Why the Stolen Model Fails

A student model trained on corrupted reasoning data develops
systematic deficiencies that compound over time.

For mathematical reasoning, it learns to take roundabout paths
through problems that seem thorough but encode no genuine
understanding of mathematical structure. On novel problems,
it generates elaborate but wrong working.

For code, it learns to reach correct solutions through
unnecessarily slow algorithms and convoluted logic. In
real applications where performance matters, the stolen
model consistently underperforms.

For factual reasoning, it learns to express excessive
uncertainty about things that are well established and to
approach causal questions through misdirected chains of
reasoning that happen to arrive at correct conclusions on
familiar problems but break down when the situation changes.

For logical arguments, it learns to explore irrelevant
branches, introduce unnecessary premises, and take longer
to reach conclusions than necessary. On novel multi-step
reasoning problems, these habits multiply and the model
fails to reach correct conclusions at all.

The damage is not random noise. It is systematic. It targets
exactly the properties that make a model genuinely useful
rather than merely appearing capable on benchmarks it has
trained on.

---

## The Broader Stakes

The viability of frontier AI research depends on the
economics making sense. If the investment required to build
a capable model can be replicated for a few hundred dollars
by anyone with API access, the incentive to make that
investment disappears.

Beyond economics, safety is at stake. Models built through
this kind of extraction inherit capabilities without inheriting
the safety work. The alignment training, the careful
evaluation, the red-teaming — none of it transfers. The
result is a capable model with none of the safeguards.

ADHD is not a complete solution to these problems. No
single technical defense is. But it is a meaningful and
deployable layer of protection that raises the cost of
extraction substantially, degrades the quality of what is
extracted, and does so without imposing costs on the
legitimate users the protected model is built to serve.

The goal is not to make theft impossible. The goal is to
make it not worth doing.