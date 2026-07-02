class CodexToken < Formula
  desc "Print and sync OpenAI Codex CLI credentials across machines (leader/follower)"
  homepage "https://github.com/krandder/homebrew-tools"
  url "https://raw.githubusercontent.com/krandder/homebrew-tools/f0fbe0ddf5d6755199cd8269d1bd05836f949cfc/codex-token"
  version "2.6.0"
  sha256 "bd5b7902b55f22ade55ee4a7987482f9103eb0215578eb808ed17b733727b55d"

  def install
    bin.install "codex-token"
  end

  test do
    assert_match "codex-token", shell_output("#{bin}/codex-token --version")
  end
end
