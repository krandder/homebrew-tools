class CodexToken < Formula
  desc "Print and sync OpenAI Codex CLI credentials across machines (leader/follower)"
  homepage "https://github.com/krandder/homebrew-tools"
  url "https://raw.githubusercontent.com/krandder/homebrew-tools/main/codex-token"
  version "2.0.0"
  sha256 "1a162654c87ee3a48ca4ec61cfa2bab3823f75d7a3d65de6ed013a6534c290f7"

  def install
    bin.install "codex-token"
  end

  test do
    assert_match "codex-token", shell_output("#{bin}/codex-token --version")
  end
end
