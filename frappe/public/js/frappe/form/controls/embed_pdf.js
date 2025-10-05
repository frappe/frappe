frappe.ui.form.ControlEmbedPdf = class ControlEmbedPdf extends frappe.ui.form.ControlAttach {
	make_input() {
		// Create button exactly like ControlAttach but with PDF-specific text
		let me = this;
		this.$input = $('<button class="btn btn-default btn-sm btn-attach">')
			.html(__("Upload PDF"))
			.prependTo(me.input_area)
			.on({
				click: function () {
					me.on_attach_click();
				},
				attach_doc_image: function () {
					me.on_attach_doc_image();
				},
			});
		this.$value = $(
			`<div class="attached-file flex justify-between align-center">
				<div class="ellipsis">
				${frappe.utils.icon("es-line-link", "sm")}
					<a class="attached-file-link" target="_blank"></a>
				</div>
				<div>
					<a class="btn btn-xs btn-default" data-action="reload_attachment">${__("Reload File")}</a>
					<a class="btn btn-xs btn-default" data-action="clear_attachment">${__("Clear")}</a>
				</div>
			</div>`
		)
			.prependTo(me.input_area)
			.toggle(false);
		this.input = this.$input.get(0);
		this.set_input_attributes();
		this.has_input = true;

		frappe.utils.bind_actions_with_object(this.$value, this);
		this.toggle_reload_button();
		
		// Create responsive PDF preview container
		this.$pdf_preview = $(`
			<div class="embed-pdf-container" style="display: none; margin-top: 10px; width: 100%;">
				<div class="pdf-preview-header" style="display: flex; justify-content: space-between; align-items: center; padding: 8px; background: #f8f9fa; border: 1px solid #dee2e6; border-radius: 8px !important;">
					<h6 style="margin: 0; color: #495057;">${__("PDF Preview")}</h6>
					<div class="pdf-controls">
						<button type="button" class="btn btn-xs btn-default" data-action="toggle_preview">
							${__("Show Preview")}
						</button>
						<button type="button" class="btn btn-xs btn-default" data-action="fullscreen_pdf" style="margin-left: 5px;">
							${__("Fullscreen")}
						</button>
					</div>
				</div>
				<div class="pdf-viewer-wrapper" style="width: 100%; position: relative; border: 1px solid #dee2e6;">
					<iframe class="pdf-viewer" style="width: 100%; height: 400px; border: none; display: block;"></iframe>
					<div class="pdf-loading text-center" style="position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%); display: none;">
						<i class="fa fa-spinner fa-spin"></i> ${__("Loading PDF...")}
					</div>
					<div class="pdf-error text-center" style="position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%); display: none; color: #dc3545;">
						<i class="fa fa-exclamation-triangle"></i> ${__("Unable to load PDF preview")}
					</div>
				</div>
			</div>
		`).insertAfter(this.$value);

		// Bind actions for PDF preview
		try {
			frappe.utils.bind_actions_with_object(this.$pdf_preview, this);
		} catch (error) {
			console.error("Failed to bind actions for PDF preview:", error);
		}
		
		// Setup responsive behavior
		this.setup_resize_handler();
		
		// Initialize EmbedPDF library loading
		this.embedpdf_loaded = false;
		this.preview_visible = true;
		this.user_toggled_preview = false; // Track if user manually toggled preview
	}

	set_upload_options() {
		super.set_upload_options();
		// Restrict to PDF files only
		this.upload_options.restrictions.allowed_file_types = ["application/pdf", ".pdf"];
	}

	set_input(value, dataurl) {
		super.set_input(value, dataurl);
		
		// Show/hide PDF preview based on value
		if (value && this.is_pdf_file(value)) {
			this.show_pdf_preview(value);
		} else {
			this.$pdf_preview.hide();
			// Reset toggle state when no PDF is present
			this.user_toggled_preview = false;
			this.preview_visible = true;
		}
	}

	is_pdf_file(filename) {
		if (!filename) return false;
		const ext = filename.toLowerCase().split('.').pop();
		return ext === 'pdf' || filename.toLowerCase().includes('.pdf');
	}

	async load_embedpdf_library() {
		if (this.embedpdf_loaded || window.EmbedPDF) {
			return true;
		}

		try {
			// Dynamically import EmbedPDF from a local copy for security
			const EmbedPDF = await import('/assets/frappe/js/embedpdf.js');
			window.EmbedPDF = EmbedPDF.default || EmbedPDF;
			this.embedpdf_loaded = true;
			return true;
		} catch (error) {
			console.error('Failed to load EmbedPDF library:', error);
			this.show_fallback_message();
			return false;
		}
	}

	show_pdf_preview(file_url) {
		// Display the PDF preview container
		this.$pdf_preview.show();
		
		const $viewer_wrapper = this.$pdf_preview.find('.pdf-viewer-wrapper');
		const $toggle_btn = this.$pdf_preview.find('[data-action="toggle_preview"]');
		
		// If user hasn't manually toggled, show preview by default
		// If user has toggled, maintain their last preference
		if (!this.user_toggled_preview) {
			this.preview_visible = true;
			$viewer_wrapper.show();
			$toggle_btn.text(__("Hide Preview"));
		} else {
			// Maintain user's previous toggle state
			if (this.preview_visible) {
				$viewer_wrapper.show();
				$toggle_btn.text(__("Hide Preview"));
			} else {
				$viewer_wrapper.hide();
				$toggle_btn.text(__("Show Preview"));
			}
		}
		
		console.log('EmbedPDF: Showing PDF preview for:', file_url);
		
		// Load PDF viewer only if preview is visible
		if (this.preview_visible) {
			// Force resize adjustment after container is visible
			setTimeout(() => {
				this.adjust_pdf_size();
			}, 100);
			
			const $viewer = this.$pdf_preview.find('.pdf-viewer');
			
			// Use native PDF viewer directly (more reliable)
			this.load_native_pdf_viewer(file_url, $viewer);
		}
	}

	adjust_pdf_size() {
		// Calculate responsive height based on container width and actual column layout
		const $container = this.$pdf_preview;
		if (!$container.is(':visible')) return;
		
		const container_width = $container.width();
		const parent_width = $container.parent().width();
		const window_width = $(window).width();
		
		let optimal_height;
		let layout_type = 'full';
		
		// Simple and reliable layout detection
		// Check if this field is in a narrow column (less than 60% of parent width)
		const width_ratio = container_width / parent_width;
		
		// Check for actual column break indicators
		const $field_wrapper = $container.closest('.frappe-control');
		const $section_body = $container.closest('.section-body');
		
		if ($field_wrapper.length && $section_body.length) {
			const section_width = $section_body.width();
			const field_width = $field_wrapper.width();
			
			// If field takes less than 70% of section width, it's likely in a column
			if (field_width < section_width * 0.7) {
				layout_type = 'half';
			}
		}
		
		// Fallback: check container width relative to viewport
		if (layout_type === 'full' && container_width < window_width * 0.6) {
			layout_type = 'half';
		}
		
		// Calculate height based on layout
		if (layout_type === 'half') {
			// Compact for columns
			optimal_height = Math.max(280, Math.min(container_width * 0.75, 400));
		} else {
			// Full width - more spacious
			optimal_height = Math.max(400, Math.min(container_width * 0.6, 600));
		}
		
		// Mobile responsiveness
		if (window_width < 768) {
			optimal_height = Math.min(optimal_height, 350);
		}
		
		// Apply the height
		const $viewer = this.$pdf_preview.find('.pdf-viewer');
		$viewer.css('height', optimal_height + 'px');
		
		// Ensure container uses full width
		$container.css('width', '100%');
		
		// Debug info
		console.log(`EmbedPDF: ${layout_type} layout, Container: ${container_width}px, Height: ${optimal_height}px`);
		
		return optimal_height;
	}

	load_native_pdf_viewer(file_url, $viewer) {
		try {
			const $loading = this.$pdf_preview.find('.pdf-loading');
			const $error = this.$pdf_preview.find('.pdf-error');
			
			$loading.show();
			$error.hide();
			
			// Show PDF directly in the iframe
			$viewer.attr('src', file_url).on('load', function() {
				$loading.hide();
				$error.hide();
			}).on('error', function() {
				$loading.hide();
				$error.show();
				// Fallback message
				$viewer.attr('src', '').html(`
					<div class="text-center" style="padding: 40px;">
						<i class="fa fa-file-pdf-o fa-3x text-muted" style="margin-bottom: 15px;"></i>
						<p class="text-muted">${__("PDF Preview")}</p>
						<a href="${file_url}" target="_blank" class="btn btn-sm btn-default">
							<i class="fa fa-external-link"></i> ${__("Open PDF")}
						</a>
					</div>
				`);
			});
			
		} catch (error) {
			console.error('Failed to load PDF preview:', error);
			const $loading = this.$pdf_preview.find('.pdf-loading');
			const $error = this.$pdf_preview.find('.pdf-error');
			$loading.hide();
			$error.show();
		}
	}

	async load_embedpdf_service(file_url, $viewer) {
		// Try EmbedPDF.com service (original implementation)
		const loaded = await this.load_embedpdf_library();
		
		if (!loaded) {
			// Fall back to native viewer
			this.load_native_pdf_viewer(file_url, $viewer);
			return;
		}

		try {
			// Create unique ID for this viewer
			const viewer_id = `pdf-viewer-${frappe.utils.get_random(8)}`;
			$viewer.html(`<div id="${viewer_id}" style="height: 100%; width: 100%;"></div>`);
			
			// Initialize EmbedPDF viewer
			const viewer = window.EmbedPDF.init({
				type: 'container',
				target: document.getElementById(viewer_id),
				src: file_url,
				settings: {
					toolbar: true,
					navigation: true,
					zoom: true,
					search: true
				}
			});

			// Store viewer reference for cleanup
			this.pdf_viewer = viewer;
			
		} catch (error) {
			console.error('Failed to initialize PDF viewer:', error);
			this.show_fallback_message();
		}
	}

	show_fallback_message() {
		const $viewer = this.$pdf_preview.find('.pdf-viewer');
		$viewer.html(`
			<div class="text-center" style="padding: 50px;">
				<p class="text-muted">${__("PDF preview is not available.")}</p>
				<p class="text-muted">${__("Click the link above to download and view the PDF.")}</p>
			</div>
		`);
	}

	async on_upload_complete(attachment) {
		// Validate that uploaded file is PDF
		if (!this.is_pdf_file(attachment.file_name)) {
			frappe.msgprint(__("Please upload only PDF files."));
			return;
		}
		
		// Call parent method
		super.on_upload_complete(attachment);
	}

	// Action handlers for buttons
	toggle_preview() {
		const $viewer_wrapper = this.$pdf_preview.find('.pdf-viewer-wrapper');
		const $toggle_btn = this.$pdf_preview.find('[data-action="toggle_preview"]');
		
		// Mark that user has manually toggled preview
		this.user_toggled_preview = true;
		
		if ($viewer_wrapper.is(':visible')) {
			$viewer_wrapper.hide();
			this.preview_visible = false;
			$toggle_btn.text(__("Show Preview"));
		} else {
			$viewer_wrapper.show();
			this.preview_visible = true;
			$toggle_btn.text(__("Hide Preview"));
			// Readjust size when showing with a small delay
			setTimeout(() => {
				this.adjust_pdf_size();
			}, 50);
		}
	}
	
	fullscreen_pdf() {
		const pdf_url = this.get_value();
		if (pdf_url) {
			// Open PDF in new tab for fullscreen viewing
			window.open(pdf_url, '_blank');
		}
	}
	
	// Handle window resize and layout changes for responsive behavior
	setup_resize_handler() {
		// Window resize handler
		$(window).on('resize.embedpdf-' + this.df.fieldname, () => {
			if (this.preview_visible && this.$pdf_preview.is(':visible')) {
				// Debounce resize events
				clearTimeout(this.resize_timeout);
				this.resize_timeout = setTimeout(() => {
					this.adjust_pdf_size();
				}, 150);
			}
		});
		
		// Form layout change observer (for dynamic layout changes)
		if (window.ResizeObserver) {
			const $form_container = this.$pdf_preview.closest('.form-layout, .form-body, .section-body');
			if ($form_container.length) {
				this.resize_observer = new ResizeObserver((entries) => {
					if (this.preview_visible && this.$pdf_preview.is(':visible')) {
						this.adjust_pdf_size();
					}
				});
				this.resize_observer.observe($form_container[0]);
			}
		}
		
		// Initial adjustment after a short delay to ensure DOM is settled
		setTimeout(() => {
			if (this.preview_visible && this.$pdf_preview.is(':visible')) {
				this.adjust_pdf_size();
			}
		}, 100);
	}
	
	destroy() {
		// Clean up resize handler
		$(window).off('resize.embedpdf-' + this.df.fieldname);
		
		// Clean up resize timeout
		if (this.resize_timeout) {
			clearTimeout(this.resize_timeout);
		}
		
		// Clean up resize observer
		if (this.resize_observer) {
			this.resize_observer.disconnect();
			this.resize_observer = null;
		}
		
		// Clean up PDF viewer if exists
		if (this.pdf_viewer && this.pdf_viewer.destroy) {
			this.pdf_viewer.destroy();
		}
		
		super.destroy && super.destroy();
	}
};