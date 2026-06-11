class ClaudeToken < Formula
  desc "Extract Claude Code authentication credentials"
  homepage "https://github.com/krandder/homebrew-tools"
  url "https://raw.githubusercontent.com/krandder/homebrew-tools/main/claude-token"
  version "1.1.1"
  sha256 "d0ac056234ab6dfb74633523602d69739a473d9198c2544833c8b211276ee3dd"

  def install
    bin.install "claude-token"
  end

  test do
    assert_predicate bin/"claude-token", :exist?
  end
end
