#!/usr/bin/env bash
# Interactive recorder for bench-stt fixtures.
#
#   Enter to start, speak, Enter to stop, then keep / re-record / skip.
#
# Records straight from the FIFINE mic at the format bench-stt requires
# (16 kHz, mono, s16) and writes <name>.wav + <name>.txt pairs.

set -uo pipefail

FIXTURES="${FIXTURES:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/tests/fixtures}"
PY="${PY:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/.venv/bin/python}"

# Room tone on the fifine at its current gain peaks around 950, so the speech
# floor sits well clear of it rather than just above zero.
SILENCE_MAX_PEAK=3000
SPEECH_MIN_PEAK=4000

BOLD=$'\e[1m'; DIM=$'\e[2m'; RED=$'\e[31m'; GREEN=$'\e[32m'; YELLOW=$'\e[33m'; OFF=$'\e[0m'

# Fixture scripts. The .txt reference is written from these on every run, so the text
# you read and the text WER scores against can never drift apart.
#
# IMPORTANT: that also means editing tests/fixtures/<name>.txt by hand is pointless —
# the next re-record overwrites it. If you misread a line and want to keep the take,
# correct the text HERE instead, so script and reference stay in sync.
#
# The `tech` line deliberately reads "for YAML parse error" without the article: on
# 2026-07-25 the recorded take omitted the "a", confirmed by listening, and all five
# benchmarked models transcribed it that way. The reference matches the audio.
names=(tech prose mixed silence)

script_for() {
    case "$1" in
    tech) cat <<'EOF'
Open GitHub and clone the repo, then run kubectl apply against the staging cluster and check the JSON output for YAML parse error in the Postgres config.
EOF
        ;;
    prose) cat <<'EOF'
I think the right move here is to ship the smaller change first, measure how it behaves for a week, and only then decide whether the larger refactor is worth the risk.
EOF
        ;;
    mixed) cat <<'EOF'
Can you review the pull request when you get a chance? The TypeScript types were wrong in the API client, so npm run build was failing in CI on Docker images built from the main branch.
EOF
        ;;
    silence) printf '' ;;
    esac
}

hint_for() {
    if [[ "$1" == silence ]]; then
        echo "Say NOTHING. Just let the room breathe for about 3 seconds."
    else
        echo "Read the text below aloud, at your normal dictation pace."
    fi
}

resolve_mic() {
    # Match on node.name so the target survives a replug (object.serial does not).
    pw-dump 2>/dev/null | "$PY" -c '
import json, sys
for obj in json.load(sys.stdin):
    props = (obj.get("info") or {}).get("props") or {}
    if props.get("media.class") != "Audio/Source":
        continue
    name = props.get("node.name", "")
    if "FIFINE" in name.upper():
        print(name)
        print(props.get("node.description", "?"))
        print(props.get("object.serial", "?"))
        break
'
}

analyse() {
    # duration, peak, RMS — a wrong-device or muted take shows up as a flat peak.
    "$PY" - "$1" <<'EOF'
import array, sys, wave

path = sys.argv[1]
with wave.open(path, "rb") as w:
    rate, width, channels, frames = (
        w.getframerate(), w.getsampwidth(), w.getnchannels(), w.getnframes()
    )
    raw = w.readframes(frames)

samples = array.array("h")
samples.frombytes(raw)
peak = max((abs(s) for s in samples), default=0)
rms = int((sum(s * s for s in samples) / len(samples)) ** 0.5) if samples else 0
seconds = frames / rate if rate else 0.0

print(f"{rate} {width} {channels} {seconds:.2f} {peak} {rms}")
EOF
}

stop_recorder() {
    # pw-cat --record exits on neither SIGINT nor SIGTERM, so escalate to KILL.
    # Safe: it keeps the WAV header's frame count patched as it writes, so a
    # killed file still opens cleanly (verified with python's wave module).
    local pid="$1"
    kill -TERM "$pid" 2>/dev/null
    for _ in 1 2 3; do
        kill -0 "$pid" 2>/dev/null || break
        sleep 0.1
    done
    kill -KILL "$pid" 2>/dev/null
    wait "$pid" 2>/dev/null
    return 0
}

record_one() {
    local name="$1" wav="$FIXTURES/$name.wav" txt="$FIXTURES/$name.txt"
    local text; text="$(script_for "$name")"
    printf '%s' "$text" > "$txt"

    while true; do
        printf '\n%s─── %s ───%s\n' "$BOLD" "$name" "$OFF"
        printf '%s%s%s\n' "$DIM" "$(hint_for "$name")" "$OFF"
        [[ -n "$text" ]] && printf '\n  %s%s%s\n' "$BOLD" "$text" "$OFF"
        printf '\n%sEnter%s to start recording (or %ss%s to skip): ' "$GREEN" "$OFF" "$YELLOW" "$OFF"
        read -r start_key
        [[ "$start_key" == s ]] && { printf '%sskipped%s\n' "$YELLOW" "$OFF"; return 0; }

        pw-cat --record --target "$MIC_NODE" \
               --rate 16000 --channels 1 --format s16 "$wav" </dev/null &>/dev/null &
        local pid=$!
        sleep 0.3
        if ! kill -0 "$pid" 2>/dev/null; then
            printf '%spw-cat died immediately — is the mic in use?%s\n' "$RED" "$OFF"
            return 1
        fi

        printf '  %s● RECORDING%s — %sEnter%s to stop: ' "$RED" "$OFF" "$GREEN" "$OFF"
        read -r _
        stop_recorder "$pid"

        read -r rate width channels seconds peak rms <<<"$(analyse "$wav")"
        printf '  %s%s Hz, %s ch, %s-byte, %ss  peak=%s rms=%s%s\n' \
            "$DIM" "$rate" "$channels" "$width" "$seconds" "$peak" "$rms" "$OFF"

        local verdict="" problem=0
        if [[ "$rate" != 16000 || "$channels" != 1 || "$width" != 2 ]]; then
            verdict="wrong format — bench-stt requires 16000 Hz / mono / s16"; problem=1
        elif [[ "$name" == silence ]]; then
            if (( peak > SILENCE_MAX_PEAK )); then
                verdict="that is not silence (peak $peak) — too loud to be room tone"; problem=1
            else
                verdict="quiet enough to serve as the hallucination check"
            fi
        elif (( peak < SPEECH_MIN_PEAK )); then
            verdict="no speech detected (peak $peak) — mic muted, or wrong device"; problem=1
        elif (( peak > 32000 )); then
            verdict="clipping (peak $peak) — back off the gain or move away from the mic"; problem=1
        elif (( $(printf '%.0f' "$seconds") < 2 )); then
            verdict="only ${seconds}s — did you stop early?"; problem=1
        else
            verdict="looks good"
        fi

        if (( problem )); then
            printf '  %s✗ %s%s\n' "$RED" "$verdict" "$OFF"
        else
            printf '  %s✓ %s%s\n' "$GREEN" "$verdict" "$OFF"
        fi

        printf '\n  %sEnter%s=keep  %sr%s=re-record  %sp%s=play back  %ss%s=skip: ' \
            "$GREEN" "$OFF" "$YELLOW" "$OFF" "$YELLOW" "$OFF" "$YELLOW" "$OFF"
        read -r choice
        case "$choice" in
        r|R) continue ;;
        p|P) pw-cat --playback "$wav" &>/dev/null; continue ;;
        s|S) rm -f "$wav"; printf '  %sskipped%s\n' "$YELLOW" "$OFF"; return 0 ;;
        *)   printf '  %skept %s%s\n' "$GREEN" "$wav" "$OFF"; return 0 ;;
        esac
    done
}

main() {
    command -v pw-cat >/dev/null || { printf '%spw-cat not found (install pipewire-bin)%s\n' "$RED" "$OFF"; exit 1; }
    [[ -x "$PY" ]] || { printf '%sno interpreter at %s%s\n' "$RED" "$PY" "$OFF"; exit 1; }
    mkdir -p "$FIXTURES"

    local mic_info; mic_info="$(resolve_mic)"
    if [[ -z "$mic_info" ]]; then
        printf '%sNo FIFINE audio source found in pw-dump.%s\n' "$RED" "$OFF"
        printf 'Available sources:\n'
        wpctl status | sed -n '/Sources:/,/Source endpoints/p'
        exit 1
    fi
    MIC_NODE="$(sed -n 1p <<<"$mic_info")"
    local mic_desc mic_serial
    mic_desc="$(sed -n 2p <<<"$mic_info")"
    mic_serial="$(sed -n 3p <<<"$mic_info")"

    printf '%sblurt fixture recorder%s\n' "$BOLD" "$OFF"
    printf 'mic:       %s%s%s (serial %s)\n' "$GREEN" "$mic_desc" "$OFF" "$mic_serial"
    printf 'node:      %s%s%s\n' "$DIM" "$MIC_NODE" "$OFF"
    printf 'format:    16000 Hz, mono, s16\n'
    printf 'fixtures:  %s\n' "$FIXTURES"
    printf '\n%sEvery take is verified for format, level and duration before it is kept.%s\n' \
        "$DIM" "$OFF"

    local targets=("${@:-}")
    [[ -z "${targets[0]:-}" ]] && targets=("${names[@]}")
    for name in "${targets[@]}"; do
        record_one "$name" || exit 1
    done

    printf '\n%s─── done ───%s\n' "$BOLD" "$OFF"
    for name in "${names[@]}"; do
        local wav="$FIXTURES/$name.wav"
        if [[ -f "$wav" ]]; then
            read -r rate width channels seconds peak rms <<<"$(analyse "$wav")"
            printf '  %-8s %ss  peak=%-6s rms=%s\n' "$name" "$seconds" "$peak" "$rms"
        else
            printf '  %-8s %sMISSING%s\n' "$name" "$YELLOW" "$OFF"
        fi
    done
    printf '\nNext: %sblurt bench-stt --models base.en%s\n' "$BOLD" "$OFF"
}

main "$@"
