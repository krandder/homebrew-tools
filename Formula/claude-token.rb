class ClaudeToken < Formula
  desc "Sync Claude Code credentials through an owner/follower vault"
  homepage "https://github.com/krandder/homebrew-tools"
  url "https://raw.githubusercontent.com/krandder/homebrew-tools/main/claude-token"
  version "2.5.0"
  sha256 "d86a83f18279c1f0b7e83ded847b73c9a5eca3309fdba8e9ab53ca7e97882550"

  def install
    bin.install "claude-token"
  end

  test do
    assert_match "claude-token 2.5.0", shell_output("#{bin}/claude-token --version")
  end
end
