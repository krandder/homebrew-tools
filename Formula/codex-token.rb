class CodexToken < Formula
  desc "Print and sync OpenAI Codex CLI credentials across machines (leader/follower)"
  homepage "https://github.com/krandder/homebrew-tools"
  url "https://raw.githubusercontent.com/krandder/homebrew-tools/cb9c1e9b98d847fc58163c6c34a391463902192d/codex-token"
  version "3.0.9"
  sha256 "2e59e3ab3148a6a164a6e661177699963fb3cf166315731fee23b7df85cf92b9"

  deprecate! date: "2026-07-18", because: "replaced by ai-token (one generic credential-sync tool: ai-token claude|codex|kimi)"
  depends_on "ai-token"

  def install
    bin.install "codex-token"
  end

  test do
    assert_match "ai-token 3.0.9", shell_output("#{bin}/codex-token --version")
  end
end
