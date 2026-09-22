from django.conf import settings
from django.db import connections
from django.db.migrations.recorder import MigrationRecorder
from django.http import HttpResponse
from django.utils.xmlutils import SimplerXMLGenerator
from io import StringIO
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView


PUBLIC_PATHS = [
    "/",
    "/discover",
    "/official",
    "/download",
    "/login",
    "/register",
]


class LiveHealthView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def get(self, request):
        try:
            connections["default"].ensure_connection()
        except Exception:
            return Response(
                {"success": False, "status": "unhealthy", "service": "api"},
                status=503,
            )

        return Response(
            {"success": True, "status": "healthy", "service": "api"},
            headers={"Cache-Control": "no-store"},
        )


class ReadyHealthView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def get(self, request):
        try:
            connections["default"].ensure_connection()
            recorder = MigrationRecorder(connections["default"])
            is_ready = recorder.has_table() and recorder.applied_migrations()
        except Exception:
            is_ready = False

        if not is_ready:
            return Response(
                {"success": False, "status": "not_ready", "service": "api"},
                status=503,
                headers={"Cache-Control": "no-store"},
            )

        return Response(
            {"success": True, "status": "ready", "service": "api"},
            headers={"Cache-Control": "no-store"},
        )


class RobotsTxtView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def get(self, request):
        content = (
            "User-agent: *\n"
            "Allow: /\n"
            "Disallow: /admin/\n"
            "Sitemap: /sitemap.xml\n"
        )
        return HttpResponse(content, content_type="text/plain; charset=utf-8")


class SitemapView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def get(self, request):
        stream = StringIO()
        generator = SimplerXMLGenerator(stream, "utf-8")
        generator.startDocument()
        generator.startElement("urlset", {"xmlns": "http://www.sitemaps.org/schemas/sitemap/0.9"})

        for path in PUBLIC_PATHS:
            generator.startElement("url", {})
            generator.addQuickElement("loc", request.build_absolute_uri(path))
            generator.addQuickElement("changefreq", "daily" if path in ("/", "/discover", "/official") else "monthly")
            generator.addQuickElement("priority", "1.0" if path == "/" else "0.8" if path in ("/discover", "/official", "/download") else "0.5")
            generator.endElement("url")

        generator.endElement("urlset")
        generator.endDocument()
        return HttpResponse(
            stream.getvalue(),
            content_type="application/xml; charset=utf-8",
            headers={"Cache-Control": "public, max-age=3600"},
        )


class ReleaseLatestView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def get(self, request):
        version = getattr(settings, "MANJI_RELEASE_VERSION", "").strip()
        download_url = getattr(settings, "MANJI_DOWNLOAD_URL", "").strip()

        if not version or not download_url:
            return Response(
                {
                    "success": False,
                    "error": {
                        "code": "release_not_configured",
                        "message": "The Windows release is not configured for this deployment.",
                    },
                },
                status=503,
                headers={"Cache-Control": "no-store"},
            )

        data = {
            "version": version,
            "download_url": download_url,
            "portable_download_url": getattr(settings, "MANJI_PORTABLE_DOWNLOAD_URL", "").strip(),
            "release_date": getattr(settings, "MANJI_RELEASE_DATE", "").strip(),
            "installer_size_bytes": getattr(settings, "MANJI_INSTALLER_SIZE_BYTES", None),
            "portable_size_bytes": getattr(settings, "MANJI_PORTABLE_SIZE_BYTES", None),
            "supported_windows": getattr(
                settings,
                "MANJI_SUPPORTED_WINDOWS",
                "Windows 10 version 1903 or later (64-bit)",
            ),
            "changelog": list(getattr(settings, "MANJI_CHANGELOG", [])),
        }
        return Response(
            {"success": True, "data": data},
            headers={"Cache-Control": "public, max-age=300"},
        )
