/**
 * Portal Signing Page - JavaScript
 * Handles signature drawing, typing, uploading and submission
 */
document.addEventListener('DOMContentLoaded', function () {
    'use strict';

    // === Elements ===
    const canvas = document.getElementById('signatureCanvas');
    const typedInput = document.getElementById('typedSignature');
    const typedPreview = document.getElementById('typedPreview');
    const uploadInput = document.getElementById('uploadSignature');
    const uploadPreview = document.getElementById('uploadPreview');
    const submitBtn = document.getElementById('submitSignature');
    const declineBtn = document.getElementById('declineBtn');
    const clearBtn = document.getElementById('clearCanvas');
    const tabBtns = document.querySelectorAll('[data-bs-toggle="tab"], .sm-sign-tab');

    if (!canvas) return; // Not on signing page

    const ctx = canvas.getContext('2d');
    let isDrawing = false;
    let lastX = 0;
    let lastY = 0;
    let hasDrawn = false;
    let activeTab = 'draw';

    // === Canvas Setup ===
    function resizeCanvas() {
        const rect = canvas.parentElement.getBoundingClientRect();
        const dpr = window.devicePixelRatio || 1;
        canvas.width = rect.width * dpr;
        canvas.height = 200 * dpr;
        canvas.style.width = rect.width + 'px';
        canvas.style.height = '200px';
        ctx.scale(dpr, dpr);
        ctx.lineWidth = 2.5;
        ctx.lineCap = 'round';
        ctx.lineJoin = 'round';
        ctx.strokeStyle = '#1a1a2e';
    }

    resizeCanvas();
    window.addEventListener('resize', function () {
        if (!hasDrawn) resizeCanvas();
    });

    // === Drawing ===
    function getPos(e) {
        const rect = canvas.getBoundingClientRect();
        const touch = e.touches ? e.touches[0] : e;
        return {
            x: touch.clientX - rect.left,
            y: touch.clientY - rect.top
        };
    }

    function startDraw(e) {
        e.preventDefault();
        isDrawing = true;
        const pos = getPos(e);
        lastX = pos.x;
        lastY = pos.y;
        ctx.beginPath();
        ctx.moveTo(lastX, lastY);
    }

    function draw(e) {
        if (!isDrawing) return;
        e.preventDefault();
        const pos = getPos(e);
        ctx.lineTo(pos.x, pos.y);
        ctx.stroke();
        lastX = pos.x;
        lastY = pos.y;
        hasDrawn = true;
    }

    function endDraw() {
        isDrawing = false;
    }

    // Mouse events
    canvas.addEventListener('mousedown', startDraw);
    canvas.addEventListener('mousemove', draw);
    canvas.addEventListener('mouseup', endDraw);
    canvas.addEventListener('mouseleave', endDraw);

    // Touch events
    canvas.addEventListener('touchstart', startDraw, { passive: false });
    canvas.addEventListener('touchmove', draw, { passive: false });
    canvas.addEventListener('touchend', endDraw);
    canvas.addEventListener('touchcancel', endDraw);

    // Clear button
    if (clearBtn) {
        clearBtn.addEventListener('click', function () {
            ctx.clearRect(0, 0, canvas.width, canvas.height);
            hasDrawn = false;
        });
    }

    // === Typed Signature ===
    if (typedInput && typedPreview) {
        typedInput.addEventListener('input', function () {
            typedPreview.textContent = this.value || '';
        });
    }

    // === Upload Signature ===
    if (uploadInput && uploadPreview) {
        uploadInput.addEventListener('change', function () {
            const file = this.files[0];
            if (!file) return;

            if (!file.type.startsWith('image/')) {
                alert('Please upload an image file (PNG, JPG, etc.)');
                this.value = '';
                return;
            }

            if (file.size > 5 * 1024 * 1024) {
                alert('File too large. Maximum 5MB.');
                this.value = '';
                return;
            }

            const reader = new FileReader();
            reader.onload = function (ev) {
                uploadPreview.src = ev.target.result;
                uploadPreview.style.display = 'block';
            };
            reader.readAsDataURL(file);
        });
    }

    // === Tab Switching ===
    tabBtns.forEach(function (btn) {
        btn.addEventListener('click', function () {
            const target = this.getAttribute('href') ||
                           this.getAttribute('data-bs-target') ||
                           this.getAttribute('data-tab') || '';
            if (target.includes('draw')) activeTab = 'draw';
            else if (target.includes('type')) activeTab = 'type';
            else if (target.includes('upload')) activeTab = 'upload';
        });
    });

    // === Get Signature Data ===
    function getSignatureData() {
        if (activeTab === 'draw') {
            if (!hasDrawn) {
                alert('Please draw your signature on the canvas.');
                return null;
            }
            // Create a temporary canvas at 1x resolution for clean export
            const tmpCanvas = document.createElement('canvas');
            const rect = canvas.getBoundingClientRect();
            tmpCanvas.width = rect.width;
            tmpCanvas.height = rect.height;
            const tmpCtx = tmpCanvas.getContext('2d');
            tmpCtx.drawImage(canvas, 0, 0, tmpCanvas.width, tmpCanvas.height);
            const dataUrl = tmpCanvas.toDataURL('image/png');
            return {
                signature: dataUrl.split(',')[1],
                signature_type: 'draw'
            };
        } else if (activeTab === 'type') {
            const text = typedInput ? typedInput.value.trim() : '';
            if (!text) {
                alert('Please type your name.');
                return null;
            }
            // Render typed text to canvas
            const tmpCanvas = document.createElement('canvas');
            tmpCanvas.width = 600;
            tmpCanvas.height = 200;
            const tmpCtx = tmpCanvas.getContext('2d');
            tmpCtx.fillStyle = '#ffffff';
            tmpCtx.fillRect(0, 0, 600, 200);
            tmpCtx.fillStyle = '#1a1a2e';
            tmpCtx.font = 'italic 48px "Dancing Script", cursive, serif';
            tmpCtx.textAlign = 'center';
            tmpCtx.textBaseline = 'middle';
            tmpCtx.fillText(text, 300, 100);
            const dataUrl = tmpCanvas.toDataURL('image/png');
            return {
                signature: dataUrl.split(',')[1],
                signature_type: 'type'
            };
        } else if (activeTab === 'upload') {
            const img = uploadPreview && uploadPreview.src ? uploadPreview : null;
            if (!img || !img.src || img.style.display === 'none') {
                alert('Please upload a signature image.');
                return null;
            }
            // Draw uploaded image to canvas
            const tmpCanvas = document.createElement('canvas');
            tmpCanvas.width = img.naturalWidth || 600;
            tmpCanvas.height = img.naturalHeight || 200;
            const tmpCtx = tmpCanvas.getContext('2d');
            tmpCtx.drawImage(img, 0, 0);
            const dataUrl = tmpCanvas.toDataURL('image/png');
            return {
                signature: dataUrl.split(',')[1],
                signature_type: 'upload'
            };
        }
        return null;
    }

    // === Submit Signature ===
    if (submitBtn) {
        submitBtn.addEventListener('click', function () {
            const data = getSignatureData();
            if (!data) return;

            const token = this.getAttribute('data-token');
            if (!token) {
                alert('Invalid signing session.');
                return;
            }

            // Disable button, show loading
            submitBtn.disabled = true;
            const origText = submitBtn.innerHTML;
            submitBtn.innerHTML = '<i class="fa fa-spinner fa-spin me-1"></i> Submitting...';

            fetch('/sign/' + token + '/submit', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    jsonrpc: '2.0',
                    method: 'call',
                    params: data,
                }),
            })
            .then(function (resp) { return resp.json(); })
            .then(function (result) {
                if (result.result && result.result.success) {
                    // Show success - hide signature section, show success msg
                    var sigSection = document.getElementById('signatureSection');
                    var successMsg = document.getElementById('successMsg');
                    if (sigSection) sigSection.style.display = 'none';
                    if (successMsg) successMsg.style.display = 'block';
                } else {
                    var error = (result.result && result.result.error) || 
                                (result.error && result.error.message) || 'Unknown error';
                    alert('Error: ' + error);
                    submitBtn.disabled = false;
                    submitBtn.innerHTML = origText;
                }
            })
            .catch(function (err) {
                alert('Network error. Please try again.');
                console.error(err);
                submitBtn.disabled = false;
                submitBtn.innerHTML = origText;
            });
        });
    }

    // === Decline ===
    if (declineBtn) {
        declineBtn.addEventListener('click', function () {
            const reason = prompt('Reason for declining (optional):');
            if (reason === null) return; // Cancelled

            const token = this.getAttribute('data-token');
            if (!token) return;

            declineBtn.disabled = true;

            fetch('/sign/' + token + '/decline', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    jsonrpc: '2.0',
                    method: 'call',
                    params: { reason: reason || '' },
                }),
            })
            .then(function (resp) { return resp.json(); })
            .then(function (result) {
                if (result.result && result.result.success) {
                    var sigSection = document.getElementById('signatureSection');
                    if (sigSection) {
                        sigSection.innerHTML =
                            '<div class="card-body text-center py-5">' +
                            '<i class="fa fa-times-circle fa-4x text-danger mb-3"></i>' +
                            '<h3>Document Declined</h3>' +
                            '<p class="text-muted">You have declined to sign this document.</p>' +
                            '</div>';
                    }
                } else {
                    alert('Error declining document. Please try again.');
                    declineBtn.disabled = false;
                }
            })
            .catch(function () {
                alert('Network error. Please try again.');
                declineBtn.disabled = false;
            });
        });
    }
});
