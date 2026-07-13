class ClaudeToken < Formula
  desc "Sync Claude Code credentials through an owner/follower vault"
  homepage "https://github.com/krandder/homebrew-tools"
  url "https://raw.githubusercontent.com/krandder/homebrew-tools/main/claude-token"
  version "2.5.7"
  sha256 "11758db4da70436543b0a56659b94415809f235181ff884248a7beddae7d18f0"

  def install
    bin.install "claude-token"
  end

  def post_install
    system bin/"claude-token", "repair-follower-wrappers"
  end

  test do
    assert_match "claude-token 2.5.7", shell_output("#{bin}/claude-token --version")
  end
end
