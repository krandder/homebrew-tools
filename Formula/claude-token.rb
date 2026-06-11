class ClaudeToken < Formula
  desc "Extract Claude Code authentication credentials"
  homepage "https://github.com/krandder/homebrew-tools"
  url "https://raw.githubusercontent.com/krandder/homebrew-tools/main/claude-token"
  version "1.1.3"
  sha256 "0a61ff13ee0dc676c148c99ae79e3b5235b11a68c38e754b6161ff1f7d5e9203"

  def install
    bin.install "claude-token"
  end

  test do
    assert_predicate bin/"claude-token", :exist?
  end
end
