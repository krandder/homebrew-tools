class ClaudeToken < Formula
  desc "Print and sync Claude Code credentials across machines (leader/follower vault client)"
  homepage "https://github.com/krandder/homebrew-tools"
  url "https://raw.githubusercontent.com/krandder/homebrew-tools/main/claude-token"
  version "2.4.3"
  sha256 "21bee23815a2b7fecb0cf478d1387e65de2322c230359d774265c1de792c2a56"

  def install
    bin.install "claude-token"
  end

  test do
    assert_predicate bin/"claude-token", :exist?
  end
end
