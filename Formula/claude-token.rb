class ClaudeToken < Formula
  desc "Extract Claude Code authentication credentials"
  homepage "https://github.com/krandder/homebrew-tools"
  url "https://raw.githubusercontent.com/krandder/homebrew-tools/main/claude-token"
  version "1.1.2"
  sha256 "bc28c1495041dc41bd24a9a0ac738fea59f21d8440c7499dc9a6c3e0cd11fd64"

  def install
    bin.install "claude-token"
  end

  test do
    assert_predicate bin/"claude-token", :exist?
  end
end
