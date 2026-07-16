class AiVaultHttp < Formula
  desc "HTTPS front-end for ai-vault (bearer-token auth, ACL-gated push/pull)"
  homepage "https://github.com/krandder/homebrew-tools"
  url "https://raw.githubusercontent.com/krandder/homebrew-tools/main/ai-vault-http"
  version "1.1.6"
  sha256 "a1b3c8ee54ab16ec705810aea152e9bf5f152717e4f48c7712fab8b42925f14e"
  depends_on "ai-vault"
  def install
    bin.install "ai-vault-http"
  end
  test do
    assert_path_exists bin/"ai-vault-http"
  end
end
