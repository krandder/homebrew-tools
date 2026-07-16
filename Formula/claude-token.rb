class ClaudeToken < Formula
  desc "Sync Claude Code credentials through an owner/follower vault"
  homepage "https://github.com/krandder/homebrew-tools"
  url "https://raw.githubusercontent.com/krandder/homebrew-tools/main/claude-token"
  version "2.5.12"
  sha256 "06d1b44ce55d7c467f1ec73f4794faeb4f2affd9955b8ecc82a7429d930196ab"

  def install
    bin.install "claude-token"
  end

  def post_install
    system bin/"claude-token", "repair-follower-wrappers"
  end

  test do
    assert_match "claude-token 2.5.12", shell_output("#{bin}/claude-token --version")
  end
end
