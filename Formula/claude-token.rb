class ClaudeToken < Formula
  desc "Extract Claude Code authentication token"
  homepage "https://github.com/krandder/homebrew-tools"
  url "https://raw.githubusercontent.com/krandder/homebrew-tools/main/claude-token"
  version "1.0.1"
  sha256 "bf62aaaee9f5ea75b712d74881253a39454b6ad5251fbc9aa11659748e0188eb"

  def install
    bin.install "claude-token"
  end

  test do
    assert_predicate bin/"claude-token", :exist?
  end
end
