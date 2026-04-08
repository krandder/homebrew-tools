class ClaudeToken < Formula
  desc "Extract Claude Code authentication credentials"
  homepage "https://github.com/krandder/homebrew-tools"
  url "https://raw.githubusercontent.com/krandder/homebrew-tools/main/claude-token"
  version "1.1.0"
  sha256 "b7027b84ab29954cd2932a8bd401e93f6d8b277ed6fccef331c3cbcbc1a1c1e0"

  def install
    bin.install "claude-token"
  end

  test do
    assert_predicate bin/"claude-token", :exist?
  end
end
