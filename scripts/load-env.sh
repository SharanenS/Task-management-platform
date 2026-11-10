#!/usr/bin/env bash
# Shared safe environment loader for Taskspace test scripts.
# Parses key=value files as data without shell interpretation (no source/eval).

load_env_file() {
    local env_file="$1"
    if [ -z "${env_file}" ] || [ ! -f "${env_file}" ]; then
        echo "ERROR: Environment file does not exist: ${env_file}" >&2
        return 1
    fi
    while IFS= read -r line || [ -n "${line}" ]; do
        # Strip trailing carriage return if any (for CRLF line endings)
        line="${line%$'\r'}"
        # Skip empty lines
        [ -z "${line}" ] && continue
        # Strip leading whitespace to inspect for comments or blank content
        local trimmed="${line#"${line%%[![:space:]]*}"}"
        case "${trimmed}" in
            \#*|"") continue ;;
        esac
        if [[ "${line}" == *"="* ]]; then
            local key="${line%%=*}"
            local val="${line#*=}"
            # Trim whitespace from key
            key="${key%"${key##*[![:space:]]}"}"
            key="${key#"${key%%[![:space:]]*}"}"
            # Strip enclosing double or single quotes if both ends match
            if [[ "${val}" =~ ^\"(.*)\"$ ]] || [[ "${val}" =~ ^\'(.*)\'$ ]]; then
                val="${BASH_REMATCH[1]}"
            fi
            # Validate key is a valid POSIX/bash identifier
            if [[ "${key}" =~ ^[a-zA-Z_][a-zA-Z0-9_]*$ ]]; then
                export "${key}=${val}"
            fi
        fi
    done < "${env_file}"
}

if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    if [ $# -lt 1 ]; then
        echo "Usage: $0 <path-to-env-file>" >&2
        exit 1
    fi
    load_env_file "$1"
fi
