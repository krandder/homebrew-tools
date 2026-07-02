class ClaudeToken < Formula
  desc "Print and sync Claude Code credentials across machines (leader/follower vault client)"
  homepage "https://github.com/krandder/homebrew-tools"
  url "https://raw.githubusercontent.com/krandder/homebrew-tools/main/claude-token"
  version "2.3.3"
  sha256 "6c415d896b6c88e97b110a80a49820c39bee722c1aac5176ab457ab9ace8c482"

  def install
    bin.install "claude-token"
  end

  test do
    assert_predicate bin/"claude-token", :exist?
  end
end
