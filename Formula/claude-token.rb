class ClaudeToken < Formula
  desc "Print and sync Claude Code credentials across machines (leader/follower vault client)"
  homepage "https://github.com/krandder/homebrew-tools"
  url "https://raw.githubusercontent.com/krandder/homebrew-tools/main/claude-token"
  version "2.4.1"
  sha256 "0a7312fe2d4ff61c20d4a7072c2328eb2249bcf85d4badc451079b4e6d3be087"

  def install
    bin.install "claude-token"
  end

  test do
    assert_predicate bin/"claude-token", :exist?
  end
end
