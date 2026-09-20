document.addEventListener("DOMContentLoaded", function () {
  var btnScan = document.getElementById("btnScan");
  var modal = document.getElementById("scanModal");
  var btnClose = document.getElementById("btnCloseScan");
  var qrImage = document.getElementById("qrImage");
  var mobileUrlText = document.getElementById("mobileUrlText");
  var scanStatus = document.getElementById("scanStatus");
  var subjectField = document.getElementById("subjectField");

  if (!btnScan) return; // page has no scan feature (no permission)

  var socket = io();

  btnScan.addEventListener("click", function () {
    fetch("/api/ocr/session/new", { method: "POST" })
      .then(function (r) { return r.json(); })
      .then(function (data) {
        if (data.error) {
          alert("អ្នកគ្មានសិទ្ធិប្រើមុខងារស្កេនទេ។");
          return;
        }
        var code = data.code;
        var mobileUrl = data.mobile_url;

        // Join the socket.io room for this pairing code
        socket.emit("join", { room: code });

        // QR code image (renders client-side via public QR API; requires the
        // PC to have normal internet access - only the image needs it)
        qrImage.src = "https://api.qrserver.com/v1/create-qr-code/?size=220x220&data=" + encodeURIComponent(mobileUrl);
        mobileUrlText.textContent = mobileUrl;
        scanStatus.classList.add("hidden");
        modal.classList.remove("hidden");
      });
  });

  btnClose.addEventListener("click", function () {
    modal.classList.add("hidden");
  });

  socket.on("ocr_result", function (data) {
    if (subjectField && data.text) {
      // Append if there's already text, otherwise fill directly
      subjectField.value = subjectField.value
        ? subjectField.value + "\n" + data.text
        : data.text;
    }
    scanStatus.classList.remove("hidden");
    setTimeout(function () { modal.classList.add("hidden"); }, 1500);
  });
});
