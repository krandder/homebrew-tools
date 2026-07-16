class ClaudeToken < Formula
  desc "Sync Claude Code credentials through an owner/follower vault"
  homepage "https://github.com/krandder/homebrew-tools"
  url "https://raw.githubusercontent.com/krandder/homebrew-tools/main/claude-token"
  version "2.5.9"
  sha256 "9bbcc820ee98da7259f189f6c25f3f3ebd2cc933aeb03c46472921b3c0e657d8"

  def install
    bin.install "claude-token"
  end

  def post_install
    system bin/"claude-token", "repair-follower-wrappers"
  end

  test do
    assert_match "claude-token 2.5.9", shell_output("#{bin}/claude-token --version")
  end
end
