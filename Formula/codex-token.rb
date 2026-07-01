class CodexToken < Formula
  desc "Print and sync OpenAI Codex CLI credentials across machines (leader/follower)"
  homepage "https://github.com/krandder/homebrew-tools"
  url "https://raw.githubusercontent.com/krandder/homebrew-tools/main/codex-token"
  version "2.2.0"
  sha256 "8d6f9a490129d661dcc9a0c182ef9e6876f17b3106e47eda01310f20988200cd"

  def install
    bin.install "codex-token"
  end

  test do
    assert_match "codex-token", shell_output("#{bin}/codex-token --version")
  end
end
