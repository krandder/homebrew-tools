class ClaudeToken < Formula
  desc "Sync Claude Code credentials through an owner/follower vault"
  homepage "https://github.com/krandder/homebrew-tools"
  url "https://raw.githubusercontent.com/krandder/homebrew-tools/main/claude-token"
  version "2.5.4"
  sha256 "b02de50f62bdd2c2b6cae69063947bf7b27430474d6b2f8d1b613be9b8b41027"

  def install
    bin.install "claude-token"
  end

  test do
    assert_match "claude-token 2.5.4", shell_output("#{bin}/claude-token --version")
  end
end
