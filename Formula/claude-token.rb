class ClaudeToken < Formula
  desc "Sync Claude Code credentials through an owner/follower vault"
  homepage "https://github.com/krandder/homebrew-tools"
  url "https://raw.githubusercontent.com/krandder/homebrew-tools/main/claude-token"
  version "2.5.13"
  sha256 "9f4c4249d55076b0ef25f40978056576b30251a3ecf67539f1d2f69fda9095f5"

  def install
    bin.install "claude-token"
  end

  def post_install
    system bin/"claude-token", "repair-follower-wrappers"
  end

  test do
    assert_match "claude-token 2.5.13", shell_output("#{bin}/claude-token --version")
  end
end
