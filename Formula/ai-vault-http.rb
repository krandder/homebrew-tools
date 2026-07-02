class AiVaultHttp < Formula
  desc "HTTPS front-end for ai-vault (bearer-token auth, ACL-gated push/pull)"
  homepage "https://github.com/krandder/homebrew-tools"
  url "https://raw.githubusercontent.com/krandder/homebrew-tools/main/ai-vault-http"
  version "1.1.0"
  sha256 "d0f25af78c25a438b43460549e387cbdf1575a0129bcf28649692456bb7d13d9"
  depends_on "ai-vault"
  def install
    bin.install "ai-vault-http"
  end
  test do
    assert_predicate bin/"ai-vault-http", :exist?
  end
end
