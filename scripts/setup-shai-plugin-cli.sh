#!/bin/bash
set -e

# Create directory for shai-plugin-cli
SHAI_HOME="${HOME}/.shai"
SHAI_BIN="${SHAI_HOME}/bin"
mkdir -p "${SHAI_BIN}"

# Determine OS and architecture
OS=$(uname -s | tr '[:upper:]' '[:lower:]')
ARCH=$(uname -m)

if [[ "${ARCH}" == "x86_64" ]]; then
  ARCH="amd64"
elif [[ "${ARCH}" == "arm64" || "${ARCH}" == "aarch64" ]]; then
  ARCH="arm64"
else
  echo "Unsupported architecture: ${ARCH}"
  exit 1
fi

if [[ "${OS}" == "darwin" ]]; then
  OS="darwin"
elif [[ "${OS}" == "linux" ]]; then
  OS="linux"
elif [[ "${OS}" =~ msys|mingw|cygwin ]]; then
  OS="windows"
  EXT=".exe"
else
  echo "Unsupported OS: ${OS}"
  exit 1
fi

# Get the latest release URL
echo "Fetching latest release information..."
LATEST_RELEASE_URL=$(curl -s https://api.github.com/repos/langgenius/shai-plugin-daemon/releases/latest | grep "browser_download_url.*shai-plugin-${OS}-${ARCH}${EXT:-}" | cut -d '"' -f 4)

if [[ -z "${LATEST_RELEASE_URL}" ]]; then
  echo "Failed to find download URL for ${OS}-${ARCH}"
  exit 1
fi

# Download the binary
echo "Downloading from ${LATEST_RELEASE_URL}..."
curl -L -o "${SHAI_BIN}/shai-plugin${EXT:-}" "${LATEST_RELEASE_URL}"

# Make it executable
chmod +x "${SHAI_BIN}/shai-plugin${EXT:-}"

# Create symlink to shai
ln -sf "${SHAI_BIN}/shai-plugin${EXT:-}" "${SHAI_BIN}/shai${EXT:-}"

# Add to PATH for GitHub Actions
if [[ -n "${GITHUB_PATH}" ]]; then
      echo "${SHAI_BIN}" >> "$GITHUB_PATH"
    echo "Added ${SHAI_BIN} to GITHUB_PATH"
fi

# For local development, add to current session PATH
export PATH="${SHAI_BIN}:${PATH}"

# Add to PATH if not already there and if not in CI environment
if [[ ":$PATH:" != *":${SHAI_BIN}:"* ]] && [[ -z "${CI}" ]]; then
  echo "Adding ${SHAI_BIN} to PATH in your profile..."
  
  # Determine shell profile file
  SHELL_PROFILE=""
  if [[ -n "$BASH_VERSION" ]]; then
    if [[ -f "$HOME/.bashrc" ]]; then
      SHELL_PROFILE="$HOME/.bashrc"
    elif [[ -f "$HOME/.bash_profile" ]]; then
      SHELL_PROFILE="$HOME/.bash_profile"
    fi
  elif [[ -n "$ZSH_VERSION" ]]; then
    SHELL_PROFILE="$HOME/.zshrc"
  fi
  
  if [[ -n "$SHELL_PROFILE" ]]; then
            echo "export PATH=\"${SHAI_BIN}:\$PATH\"" >> "$SHELL_PROFILE"
        echo "Added ${SHAI_BIN} to PATH in ${SHELL_PROFILE}"
        echo "Please run 'source ${SHELL_PROFILE}' or start a new terminal session to use shai-plugin-cli"
    else
        echo "Could not determine shell profile. Please add ${SHAI_BIN} to your PATH manually"
  fi
fi

echo "shai-plugin-cli has been installed to ${SHAI_BIN}/shai-plugin${EXT:-}"
echo "Version information:"
"${SHAI_BIN}/shai-plugin${EXT:-}" version

# Create a GitHub Actions environment file to make the binary available in subsequent steps
if [[ -n "${GITHUB_ENV}" ]]; then
  echo "PATH=${SHAI_BIN}:${PATH}" >> "$GITHUB_ENV"
  echo "Updated PATH in GITHUB_ENV for subsequent steps"
fi
