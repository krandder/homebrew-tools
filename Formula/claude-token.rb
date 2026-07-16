class ClaudeToken < Formula
  desc "Sync Claude Code credentials through an owner/follower vault"
  homepage "https://github.com/krandder/homebrew-tools"
  url "https://raw.githubusercontent.com/krandder/homebrew-tools/main/claude-token"
  version "2.5.15"
  sha256 "39d664e11b5f0730c2419bb2e0154ef893038bab9fca1d0975ce890bf4024823"

  def install
    bin.install "claude-token"
  end

  def post_install
    system bin/"claude-token", "repair-follower-wrappers"
  end

  test do
    assert_match "claude-token 2.5.15", shell_output("#{bin}/claude-token --version")
  end
end
