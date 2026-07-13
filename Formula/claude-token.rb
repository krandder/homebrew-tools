class ClaudeToken < Formula
  desc "Sync Claude Code credentials through an owner/follower vault"
  homepage "https://github.com/krandder/homebrew-tools"
  url "https://raw.githubusercontent.com/krandder/homebrew-tools/main/claude-token"
  version "2.5.8"
  sha256 "86d20d1ff38a2aed6a418ee8556513a76ed3d7a642e4e3272d145b7931d09dbb"

  def install
    bin.install "claude-token"
  end

  def post_install
    system bin/"claude-token", "repair-follower-wrappers"
  end

  test do
    assert_match "claude-token 2.5.8", shell_output("#{bin}/claude-token --version")
  end
end
