class ClaudeToken < Formula
  desc "Sync Claude Code credentials through an owner/follower vault"
  homepage "https://github.com/krandder/homebrew-tools"
  url "https://raw.githubusercontent.com/krandder/homebrew-tools/main/claude-token"
  version "2.5.5"
  sha256 "e03cfc0224e73a0fee32a41ce127bfc496c1ba82a2d3de1c1c491347ba8f58ff"

  def install
    bin.install "claude-token"
  end

  test do
    assert_match "claude-token 2.5.5", shell_output("#{bin}/claude-token --version")
  end
end
