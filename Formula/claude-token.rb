class ClaudeToken < Formula
  desc "Sync Claude Code credentials through an owner/follower vault"
  homepage "https://github.com/krandder/homebrew-tools"
  url "https://raw.githubusercontent.com/krandder/homebrew-tools/main/claude-token"
  version "3.0.7"
  sha256 "75e8a46c0ec9a24654a6a22de0f67eeb5ad8dfbd082ab29a02d07b1a66e18d73"

  deprecate! date: "2026-07-18", because: "replaced by ai-token (one generic credential-sync tool: ai-token claude|codex|kimi)"
  depends_on "ai-token"

  def install
    bin.install "claude-token"
  end

  def post_install
    system bin/"claude-token", "repair-follower-wrappers"
  end

  test do
    assert_match "claude-token 3.0.7", shell_output("#{bin}/claude-token --version")
  end
end
