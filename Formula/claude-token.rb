class ClaudeToken < Formula
  desc "Sync Claude Code credentials through an owner/follower vault"
  homepage "https://github.com/krandder/homebrew-tools"
  url "https://raw.githubusercontent.com/krandder/homebrew-tools/main/claude-token"
  version "2.5.11"
  sha256 "8c3f458b8aab10c82fd03b50bfc4583b56a5c86ea116e64a3b47f1c3da9df21d"

  def install
    bin.install "claude-token"
  end

  def post_install
    system bin/"claude-token", "repair-follower-wrappers"
  end

  test do
    assert_match "claude-token 2.5.11", shell_output("#{bin}/claude-token --version")
  end
end
