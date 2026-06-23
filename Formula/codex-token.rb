class CodexToken < Formula
  desc "Print and sync OpenAI Codex CLI credentials across machines (leader/follower)"
  homepage "https://github.com/krandder/homebrew-tools"
  url "https://raw.githubusercontent.com/krandder/homebrew-tools/main/codex-token"
  version "2.0.0"
  sha256 "baff8a29712c47fce25f6618b63e59374dfdb2cae884dd98c4e28fd0019108b0"

  def install
    bin.install "codex-token"
  end

  test do
    assert_match "codex-token", shell_output("#{bin}/codex-token --version")
  end
end
