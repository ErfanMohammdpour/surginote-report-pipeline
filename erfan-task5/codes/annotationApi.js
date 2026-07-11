/**
 * Annotation API Service
 * Handles all API communication related to video annotations
 * Following Single Responsibility Principle (SOLID)
 */
import axios from 'axios';

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8001';

/**
 * Get auth token from localStorage
 * @returns {Object} Authorization header object
 */
const getAuthHeader = () => {
  const token = localStorage.getItem('token');
  return token ? { Authorization: `Bearer ${token}` } : {};
};

/**
 * Create axios instance with default config
 */
const apiClient = axios.create({
  baseURL: API_BASE,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Add auth token to all requests
apiClient.interceptors.request.use((config) => {
  const authHeaders = getAuthHeader();
  config.headers = { ...config.headers, ...authHeaders };
  return config;
});

// Handle 401 unauthorized responses globally
// Note: Instead of redirecting, we trigger the re-auth flow via custom event
// This allows users to recover their session without losing work
apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      console.warn('[AnnotationAPI] Received 401 Unauthorized - session may have expired');
      
      // Dispatch custom event to trigger re-auth dialog
      // The AuthProvider listens for this and shows the re-auth dialog
      window.dispatchEvent(new CustomEvent('auth:session-expired'));
    }
    return Promise.reject(error);
  }
);

/**
 * Annotation History API Interface
 */
export const annotationApi = {
  /**
   * Get annotation history for a video
   * @param {number} videoId - Video ID
   * @returns {Promise<Array>} List of annotation history entries
   */
  async getVideoAnnotationHistory(videoId) {
    const response = await apiClient.get(`/videos/${videoId}/annotation-history`);
    return response.data;
  },

  /**
   * Create a new annotation history entry
   * @param {number} videoId - Video ID
   * @param {Object} annotation - Annotation data
   * @param {string} annotation.created_by - Name of person who created the annotation
   * @param {string} annotation.annotation_data - JSON string of annotation data
   * @returns {Promise<Object>} Created annotation history entry
   */
  async createAnnotationHistory(videoId, annotation) {
    const response = await apiClient.post(`/videos/${videoId}/annotation-history`, annotation);
    return response.data;
  },

  /**
   * Delete an annotation history entry
   * @param {number} historyId - Annotation history ID
   * @returns {Promise<void>}
   */
  async deleteAnnotationHistory(historyId) {
    await apiClient.delete(`/annotation-history/${historyId}`);
  },

  /**
   * Share an annotation history entry with contacts
   * @param {number} historyId - Annotation history ID
   * @param {Object} shareData - Share data
   * @param {Array<number>} shareData.contact_ids - Array of contact IDs
   * @param {string} shareData.message - Optional message
   * @returns {Promise<Object>} Share result
   */
  async shareAnnotationHistory(historyId, shareData) {
    const response = await apiClient.post(`/annotation-history/${historyId}/share`, shareData);
    return response.data;
  },

  /**
   * Export annotations for a video as Excel file
   * @param {number} videoId - Video ID
   * @param {string} videoName - Video name for the filename
   * @returns {Promise<void>} Downloads the Excel file
   */
  async exportAnnotationExcel(videoId, videoName = 'video') {
    try {
      const response = await apiClient.get(`/videos/${videoId}/annotation-export`, {
        responseType: 'blob',
      });
      
      // Create download link
      const blob = new Blob([response.data], {
        type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
      });
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      
      // Extract filename from Content-Disposition header or generate one
      const contentDisposition = response.headers['content-disposition'];
      let filename = `annotation_export_${videoName.replace(/[^a-zA-Z0-9]/g, '_')}.xlsx`;
      
      if (contentDisposition) {
        const filenameMatch = contentDisposition.match(/filename[^;=\n]*=((['"]).*?\2|[^;\n]*)/);
        if (filenameMatch && filenameMatch[1]) {
          filename = filenameMatch[1].replace(/['"]/g, '');
        }
      }
      
      link.href = url;
      link.setAttribute('download', filename);
      document.body.appendChild(link);
      link.click();
      
      // Cleanup
      link.parentNode.removeChild(link);
      window.URL.revokeObjectURL(url);
      
      return { success: true, filename };
    } catch (error) {
      console.error('Error exporting annotation:', error);
      throw error;
    }
  },

  /**
   * Import annotations from an Excel file
   * @param {number} videoId - Video ID to import annotations to
   * @param {File} file - Excel file to import
   * @param {string} createdBy - Name of person importing
   * @param {string} description - Optional description
   * @returns {Promise<Object>} Import result with summary
   */
  async importAnnotationExcel(videoId, file, createdBy, description = null) {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('video_id', videoId.toString());
    formData.append('created_by', createdBy);
    if (description) {
      formData.append('description', description);
    }
    
    const response = await apiClient.post('/annotations/import', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });
    
    return response.data;
  },
};

export default annotationApi;

