class CodexToken < Formula
  desc "Print and sync OpenAI Codex CLI credentials across machines (leader/follower)"
  homepage "https://github.com/krandder/homebrew-tools"
  url "https://raw.githubusercontent.com/krandder/homebrew-tools/04401e3d6d45c7f43ddf1fa7a4c4acdae77b91ce/codex-token"
  version "2.6.0"
  revision 1
  sha256 "1877ae1ea6dfc4336ff88dc03fcfd34a6b1ea75a295f2d75d279eb75c15d8b24"

  deprecate! date: "2026-07-18", because: "replaced by ai-token (one generic credential-sync tool: ai-token claude|codex|kimi)"

  def install
    bin.install "codex-token"
  end

  test do
    assert_match "codex-token", shell_output("#{bin}/codex-token --version")
  end
end
