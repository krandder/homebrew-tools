class ClaudeToken < Formula
  desc "Sync Claude Code credentials through an owner/follower vault"
  homepage "https://github.com/krandder/homebrew-tools"
  url "https://raw.githubusercontent.com/krandder/homebrew-tools/main/claude-token"
  version "2.5.1"
  sha256 "13e8f9ba3377b8f95b879c439ddca192688b62875263abc6f9f74afddbff01e9"

  def install
    bin.install "claude-token"
  end

  test do
    assert_match "claude-token 2.5.1", shell_output("#{bin}/claude-token --version")
  end
end
