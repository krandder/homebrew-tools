class ClaudeToken < Formula
  desc "Sync Claude Code credentials through an owner/follower vault"
  homepage "https://github.com/krandder/homebrew-tools"
  url "https://raw.githubusercontent.com/krandder/homebrew-tools/main/claude-token"
  version "2.5.3"
  sha256 "e0c2603705f53f36b5be3dbed9cf199db557e501d1f79e2f1d02658ef562c6be"

  def install
    bin.install "claude-token"
  end

  test do
    assert_match "claude-token 2.5.3", shell_output("#{bin}/claude-token --version")
  end
end
