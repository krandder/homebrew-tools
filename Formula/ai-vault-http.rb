class AiVaultHttp < Formula
  desc "HTTPS front-end for ai-vault (bearer-token auth, ACL-gated push/pull)"
  homepage "https://github.com/krandder/homebrew-tools"
  url "https://raw.githubusercontent.com/krandder/homebrew-tools/main/ai-vault-http"
  version "1.2.5"
  sha256 "1a197bbea93b49b6efca8ac74f786c00b92209c0da98492acb21ba36fda1abd5"
  depends_on "ai-vault"
  def install
    bin.install "ai-vault-http"
  end
  test do
    assert_path_exists bin/"ai-vault-http"
  end
end
