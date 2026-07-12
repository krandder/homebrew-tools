class ClaudeToken < Formula
  desc "Sync Claude Code credentials through an owner/follower vault"
  homepage "https://github.com/krandder/homebrew-tools"
  url "https://raw.githubusercontent.com/krandder/homebrew-tools/main/claude-token"
  version "2.5.2"
  sha256 "d31ae5715483a72125310088f0c266c514f0770a232b0879e4240d10ee9efe7f"

  def install
    bin.install "claude-token"
  end

  test do
    assert_match "claude-token 2.5.2", shell_output("#{bin}/claude-token --version")
  end
end
