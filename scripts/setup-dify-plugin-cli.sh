# download dify-plugin-cli from https://github.com/langgenius/dify-plugin-daemon/releases
# and install it to ~/.dify/bin

# download the latest release
#!/bin/bash
set -e

# Create directory for dify-plugin-cli
DIFY_HOME="${HOME}/.dify"
DIFY_BIN="${DIFY_HOME}/bin"
mkdir -p "${DIFY_BIN}"

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
LATEST_RELEASE_URL=$(curl -s https://api.github.com/repos/langgenius/dify-plugin-daemon/releases/latest | grep "browser_download_url.*dify-plugin-${OS}-${ARCH}${EXT:-}" | cut -d '"' -f 4)

if [[ -z "${LATEST_RELEASE_URL}" ]]; then
  echo "Failed to find download URL for ${OS}-${ARCH}"
  exit 1
fi

# Download the binary
echo "Downloading from ${LATEST_RELEASE_URL}..."
curl -L -o "${DIFY_BIN}/dify-plugin${EXT:-}" "${LATEST_RELEASE_URL}"

# Make it executable
chmod +x "${DIFY_BIN}/dify-plugin${EXT:-}"

# Create symlink to dify
ln -sf "${DIFY_BIN}/dify-plugin${EXT:-}" "${DIFY_BIN}/dify${EXT:-}"

# Add to PATH for the current session
export PATH="${PATH}:${DIFY_BIN}"

# Add to PATH if not already there and if not in CI environment
if [[ ":$PATH:" != *":${DIFY_BIN}:"* ]] && [[ -z "${CI}" ]]; then
  echo "Adding ${DIFY_BIN} to PATH in your profile..."
  
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
    echo "export PATH=\"\$PATH:${DIFY_BIN}\"" >> "$SHELL_PROFILE"
    echo "Added ${DIFY_BIN} to PATH in ${SHELL_PROFILE}"
    echo "Please run 'source ${SHELL_PROFILE}' or start a new terminal session to use dify-plugin-cli"
  else
    echo "Could not determine shell profile. Please add ${DIFY_BIN} to your PATH manually"
  fi
else
  echo "PATH has been updated for the current session"
fi

echo "dify-plugin-cli has been installed to ${DIFY_BIN}/dify-plugin${EXT:-}"
echo "Version information:"
"${DIFY_BIN}/dify-plugin${EXT:-}" version
