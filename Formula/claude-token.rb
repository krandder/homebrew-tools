class ClaudeToken < Formula
  desc "Print and sync Claude Code credentials across machines (leader/follower vault client)"
  homepage "https://github.com/krandder/homebrew-tools"
  url "https://raw.githubusercontent.com/krandder/homebrew-tools/main/claude-token"
  version "2.2.0"
  sha256 "47b8f3a780eae93d27b6b044067451bc7d732767f9569dd52373a87f43a0f13a"

  def install
    bin.install "claude-token"
  end

  test do
    assert_predicate bin/"claude-token", :exist?
  end
end
