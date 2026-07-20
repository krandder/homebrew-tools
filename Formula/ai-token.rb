class AiToken < Formula
  desc "One credential-sync tool for AI CLIs (claude, codex, kimi) via the vault"
  homepage "https://github.com/krandder/homebrew-tools"
  url "https://raw.githubusercontent.com/krandder/homebrew-tools/main/ai-token"
  version "3.0.8"
  sha256 "63e063482c1b8feee7a8626af54a290cdbdb69adb863f7ae83a6065c075723f1"

  def install
    bin.install "ai-token"
    # argv0 dispatch: ai-token picks its backend from the shim's basename
    bin.install_symlink bin/"ai-token" => "claude-token"
    bin.install_symlink bin/"ai-token" => "codex-token"
    bin.install_symlink bin/"ai-token" => "kimi-token"
  end

  test do
    assert_match "ai-token 3.0.8", shell_output("#{bin}/ai-token --version")
    assert_match "claude-token 3.0.8", shell_output("#{bin}/claude-token --version")
  end
end
