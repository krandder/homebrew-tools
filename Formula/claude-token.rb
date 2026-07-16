class ClaudeToken < Formula
  desc "Sync Claude Code credentials through an owner/follower vault"
  homepage "https://github.com/krandder/homebrew-tools"
  url "https://raw.githubusercontent.com/krandder/homebrew-tools/main/claude-token"
  version "2.5.10"
  sha256 "c73e8ac87da6153623f4650d3e5b390c41adaaa80612102f0493e03752d3cca1"

  def install
    bin.install "claude-token"
  end

  def post_install
    system bin/"claude-token", "repair-follower-wrappers"
  end

  test do
    assert_match "claude-token 2.5.10", shell_output("#{bin}/claude-token --version")
  end
end
