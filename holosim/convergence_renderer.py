"""Dependency-free HTML rendering for observed convergence runs."""

from __future__ import annotations

from html import escape
from typing import Any, Mapping


def _text(value: Any) -> str:
    if value is None:
        return "None"

    return escape(str(value), quote=True)


def render_convergence_html(
    observed: Mapping[str, Any],
) -> str:
    """Render an observed convergence model as standalone HTML."""
    if not isinstance(observed, Mapping):
        raise TypeError("observed must be a mapping")

    iterations = observed.get("iterations", [])

    if not isinstance(iterations, list):
        raise TypeError("observed iterations must be a list")

    iteration_sections: list[str] = []

    for iteration in iterations:
        if not isinstance(iteration, Mapping):
            raise TypeError("each iteration must be a mapping")

        number = _text(iteration.get("number"))
        status = _text(iteration.get("status"))
        difference = _text(iteration.get("difference"))
        builder_invoked = _text(
            iteration.get("builder_invoked")
        )
        verification_passed = _text(
            iteration.get("verification_passed")
        )
        builder_receipt_hash = _text(
            iteration.get("builder_receipt_hash")
        )

        iteration_sections.append(
            f"""
            <section
                class="iteration"
                data-status="{status}"
            >
                <div class="iteration-heading">
                    <h2>Iteration {number}</h2>
                    <span class="status">{status}</span>
                </div>

                <dl>
                    <div>
                        <dt>Observed difference</dt>
                        <dd>{difference}</dd>
                    </div>
                    <div>
                        <dt>Builder invoked</dt>
                        <dd>{builder_invoked}</dd>
                    </div>
                    <div>
                        <dt>Verification passed</dt>
                        <dd>{verification_passed}</dd>
                    </div>
                    <div>
                        <dt>Builder receipt</dt>
                        <dd><code>{builder_receipt_hash}</code></dd>
                    </div>
                </dl>
            </section>
            """
        )

    rendered_iterations = "\n".join(iteration_sections)

    return f"""<!doctype html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta
        name="viewport"
        content="width=device-width, initial-scale=1"
    >
    <title>HOLO/Sim Convergence Observer</title>

    <style>
        :root {{
            color-scheme: dark;
            font-family:
                Inter,
                ui-sans-serif,
                system-ui,
                sans-serif;
        }}

        body {{
            margin: 0;
            min-height: 100vh;
            padding: 2rem;
            color: #eef4ff;
            background:
                radial-gradient(
                    circle at 50% -10%,
                    rgba(91, 56, 180, 0.22),
                    transparent 42rem
                ),
                radial-gradient(
                    circle at 85% 30%,
                    rgba(0, 190, 255, 0.08),
                    transparent 32rem
                ),
                #04050a;
            line-height: 1.5;
        }}

        main {{
            max-width: 60rem;
            margin: 0 auto;
        }}

        header,
        .summary,
        .iteration {{
            border: 1px solid rgba(180, 198, 255, 0.18);
            border-radius: 0.9rem;
            padding: 1.25rem;
            margin-bottom: 1rem;
            background: rgba(7, 9, 18, 0.78);
            box-shadow:
                inset 0 0 2rem rgba(90, 66, 180, 0.04),
                0 0 2rem rgba(0, 0, 0, 0.32);
            backdrop-filter: blur(12px);
        }}

        h1,
        h2,
        p {{
            margin-top: 0;
        }}

        header {{
            position: relative;
            overflow: hidden;
        }}

        header::before {{
            content: "";
            position: absolute;
            width: 18rem;
            height: 18rem;
            top: -12rem;
            right: -6rem;
            border-radius: 50%;
            background:
                radial-gradient(
                    circle,
                    rgba(255, 183, 77, 0.3),
                    rgba(130, 80, 255, 0.12) 38%,
                    transparent 68%
                );
            filter: blur(10px);
            pointer-events: none;
        }}

        .toolbar {{
            display: flex;
            justify-content: flex-end;
            margin-bottom: 1rem;
        }}

        #sound-toggle {{
            border: 1px solid rgba(126, 224, 255, 0.45);
            border-radius: 999px;
            padding: 0.55rem 1rem;
            color: #dff9ff;
            background: rgba(0, 155, 210, 0.1);
            cursor: pointer;
        }}

        #sound-toggle:hover {{
            background: rgba(0, 155, 210, 0.18);
        }}

        #sound-toggle[aria-pressed="true"] {{
            border-color: rgba(255, 193, 100, 0.65);
            color: #ffe8bd;
            background: rgba(255, 151, 50, 0.12);
        }}

        .summary {{
            display: grid;
            grid-template-columns:
                repeat(auto-fit, minmax(12rem, 1fr));
            gap: 1rem;
        }}

        .summary div,
        dl div {{
            min-width: 0;
        }}

        .label,
        dt {{
            font-size: 0.8rem;
            text-transform: uppercase;
            letter-spacing: 0.08em;
            color: #8793ad;
        }}

        .value,
        dd {{
            margin: 0.25rem 0 0;
            overflow-wrap: anywhere;
        }}

        .iteration {{
            position: relative;
            transition:
                border-color 300ms ease,
                box-shadow 300ms ease;
        }}

        .iteration[data-status="CORRECTED"] {{
            border-color: rgba(78, 220, 255, 0.34);
        }}

        .iteration[data-status="CONVERGED"] {{
            border-color: rgba(255, 188, 82, 0.34);
        }}

        .iteration[data-status="FAILED"] {{
            border-color: rgba(255, 75, 110, 0.4);
        }}

        .iteration-heading {{
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 1rem;
        }}

        .status {{
            border: 1px solid currentColor;
            border-radius: 999px;
            padding: 0.25rem 0.65rem;
            font-size: 0.8rem;
        }}

        [data-status="CORRECTED"] .status {{
            color: #77e9ff;
        }}

        [data-status="CONVERGED"] .status {{
            color: #ffd38b;
        }}

        [data-status="FAILED"] .status {{
            color: #ff7893;
        }}

        dl {{
            display: grid;
            gap: 1rem;
            margin-bottom: 0;
        }}

        code {{
            overflow-wrap: anywhere;
            color: #bfc9df;
        }}

        @media (prefers-reduced-motion: reduce) {{
            *,
            *::before,
            *::after {{
                scroll-behavior: auto;
                transition: none !important;
                animation: none !important;
            }}
        }}
    </style>
</head>

<body>
    <main>
        <div class="toolbar">
            <button
                id="sound-toggle"
                type="button"
                aria-pressed="false"
            >
                Enable sound
            </button>
        </div>

        <header>
            <p class="label">Goal</p>
            <h1>{_text(observed.get("goal"))}</h1>
            <p>
                Observable convergence history derived from a
                version-bound receipt.
            </p>
        </header>

        <section class="summary">
            <div>
                <p class="label">Status</p>
                <p class="value">
                    {_text(observed.get("status"))}
                </p>
            </div>

            <div>
                <p class="label">Terminal reason</p>
                <p class="value">
                    {_text(observed.get("terminal_reason"))}
                </p>
            </div>

            <div>
                <p class="label">Iterations</p>
                <p class="value">
                    {_text(observed.get("iteration_count"))}
                </p>
            </div>

            <div>
                <p class="label">Corrections</p>
                <p class="value">
                    {_text(observed.get("correction_count"))}
                </p>
            </div>

            <div>
                <p class="label">Receipt</p>
                <p class="value">
                    <code>
                        {_text(observed.get("receipt_hash"))}
                    </code>
                </p>
            </div>
        </section>

        {rendered_iterations}
    </main>

    <script>
        const soundToggle = document.getElementById(
            "sound-toggle"
        );

        let audioContext = null;
        let soundEnabled = false;

        const toneDefinitions = {{
            OBSERVED: {{
                frequencies: [220.0],
                duration: 1.8,
            }},
            CORRECTED: {{
                frequencies: [261.63, 329.63],
                duration: 2.4,
            }},
            CONVERGED: {{
                frequencies: [196.0, 293.66, 392.0],
                duration: 3.2,
            }},
            FAILED: {{
                frequencies: [233.08, 246.94],
                duration: 2.2,
            }},
        }};

        function createAudioContext() {{
            if (audioContext === null) {{
                const AudioContextClass =
                    window.AudioContext ||
                    window.webkitAudioContext;

                audioContext = new AudioContextClass();
            }}

            return audioContext;
        }}

        function playChime(status, delay = 0) {{
            const definition =
                toneDefinitions[status] ||
                toneDefinitions.OBSERVED;

            const context = createAudioContext();
            const startTime = context.currentTime + delay;

            definition.frequencies.forEach(
                (frequency, index) => {{
                    const oscillator =
                        context.createOscillator();
                    const gain = context.createGain();

                    oscillator.type = "sine";
                    oscillator.frequency.setValueAtTime(
                        frequency,
                        startTime
                    );

                    gain.gain.setValueAtTime(
                        0.0001,
                        startTime
                    );
                    gain.gain.exponentialRampToValueAtTime(
                        0.035 / (index + 1),
                        startTime + 0.08
                    );
                    gain.gain.exponentialRampToValueAtTime(
                        0.0001,
                        startTime + definition.duration
                    );

                    oscillator.connect(gain);
                    gain.connect(context.destination);

                    oscillator.start(startTime);
                    oscillator.stop(
                        startTime + definition.duration
                    );
                }}
            );
        }}

        function playObservedSequence() {{
            const iterations = document.querySelectorAll(
                ".iteration[data-status]"
            );

            iterations.forEach((iteration, index) => {{
                const status =
                    iteration.dataset.status || "OBSERVED";

                playChime(status, index * 1.2);
            }});
        }}

        soundToggle.addEventListener("click", async () => {{
            const context = createAudioContext();

            if (context.state === "suspended") {{
                await context.resume();
            }}

            soundEnabled = !soundEnabled;

            soundToggle.setAttribute(
                "aria-pressed",
                String(soundEnabled)
            );

            soundToggle.textContent = soundEnabled
                ? "Sound enabled"
                : "Enable sound";

            if (soundEnabled) {{
                playObservedSequence();
            }}
        }});
    </script>
</body>
</html>
"""