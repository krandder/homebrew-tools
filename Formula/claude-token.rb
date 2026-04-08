class ClaudeToken < Formula
  desc "Extract Claude Code authentication token"
  homepage "https://github.com/krandder/homebrew-tools"
  url "https://raw.githubusercontent.com/krandder/homebrew-tools/main/claude-token"
  version "1.0.0"
  sha256 "42355e991fd037a595cbbd14d82cfa918760838e1d5e933278a1bdbbf3903dc9"

  depends_on "python@3"

  def install
    bin.install "claude-token"
  end

  test do
    assert_predicate bin/"claude-token", :exist?
  end
end
