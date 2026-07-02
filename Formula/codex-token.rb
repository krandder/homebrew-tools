class CodexToken < Formula
  desc "Print and sync OpenAI Codex CLI credentials across machines (leader/follower)"
  homepage "https://github.com/krandder/homebrew-tools"
  url "https://raw.githubusercontent.com/krandder/homebrew-tools/main/codex-token"
  version "2.5.0"
  sha256 "0325ca22cd0c5af8afcc56c5cec50dd9fc3b70345a4dae40d965e4d9fdf65c26"

  def install
    bin.install "codex-token"
  end

  test do
    assert_match "codex-token", shell_output("#{bin}/codex-token --version")
  end
end
