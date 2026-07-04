class ClaudeToken < Formula
  desc "Print and sync Claude Code credentials across machines (leader/follower vault client)"
  homepage "https://github.com/krandder/homebrew-tools"
  url "https://raw.githubusercontent.com/krandder/homebrew-tools/main/claude-token"
  version "2.4.4"
  sha256 "4d8ed1847e2dfb4619c568edcb9c2cbb79df26eba9b966735619710e99609087"

  def install
    bin.install "claude-token"
  end

  test do
    assert_predicate bin/"claude-token", :exist?
  end
end
