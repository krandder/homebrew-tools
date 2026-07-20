class AiVaultHttp < Formula
  desc "HTTPS front-end for ai-vault (bearer-token auth, ACL-gated push/pull)"
  homepage "https://github.com/krandder/homebrew-tools"
  url "https://raw.githubusercontent.com/krandder/homebrew-tools/main/ai-vault-http"
  version "1.2.3"
  sha256 "82a79b2cd290a6f34296761fdda11dee364914d0325e4decc5204459d4e1067f"
  depends_on "ai-vault"
  def install
    bin.install "ai-vault-http"
  end
  test do
    assert_path_exists bin/"ai-vault-http"
  end
end
