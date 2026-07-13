class ClaudeToken < Formula
  desc "Sync Claude Code credentials through an owner/follower vault"
  homepage "https://github.com/krandder/homebrew-tools"
  url "https://raw.githubusercontent.com/krandder/homebrew-tools/main/claude-token"
  version "2.5.6"
  sha256 "1da4b4d28d49a46d5ecc0c1e201b716b5246a34d413555d0c73666c79b5404fe"

  def install
    bin.install "claude-token"
  end

  test do
    assert_match "claude-token 2.5.6", shell_output("#{bin}/claude-token --version")
  end
end
