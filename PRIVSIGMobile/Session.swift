import Foundation
import Combine

@MainActor final class Session: ObservableObject {
    @Published var profile: Profile?
    @Published var revision = 0
    @Published var connection = "Rozłączono"
    private var token = ""
    private var base: URL?
    private var socket: URLSessionWebSocketTask?
    private var listener: Task<Void, Never>?
    private let transport = URLSession(configuration: .ephemeral)

    func login(server: String, username: String, password: String) async throws {
        guard let url = URL(string: server.trimmingCharacters(in: .whitespacesAndNewlines)),
              url.scheme == "https", url.host != nil, url.user == nil, url.password == nil,
              url.query == nil, url.fragment == nil else {
            throw APIError(status: 0, message: "Podaj adres HTTPS serwera szkoły.")
        }
        clear()
        base = url
        do {
            let reply: LoginReply = try await request("auth/login", method: "POST", body: ["username": .string(username), "password": .string(password)])
            token = reply.token
            let me: Profile = try await request("me")
            profile = me
            connect()
        } catch { clear(); throw error }
    }
    func request<T: Decodable>(_ path: String, method: String = "GET", body: [String: Value]? = nil) async throws -> T {
        guard let base else { throw APIError(status: 0, message: "Brak serwera.") }
        var req = URLRequest(url: base.appendingPathComponent(path))
        req.httpMethod = method; req.timeoutInterval = 25
        req.cachePolicy = .reloadIgnoringLocalCacheData
        if !token.isEmpty { req.setValue("Bearer " + token, forHTTPHeaderField: "Authorization") }
        if let body { req.httpBody = try JSONEncoder().encode(body); req.setValue("application/json", forHTTPHeaderField: "Content-Type") }
        let (data, response) = try await transport.data(for: req)
        let status = (response as? HTTPURLResponse)?.statusCode ?? 0
        guard (200..<300).contains(status) else {
            if status == 401 { clear() }
            let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any]
            let message = json?["detail"] as? String ?? "Błąd serwera (\(status)). Sprawdź dane i uprawnienia."
            throw APIError(status: status, message: message)
        }
        return try JSONDecoder().decode(T.self, from: data)
    }
    func save(_ module: String, row: Row?, data: [String: Value]) async throws {
        var body: [String: Value] = ["data": .object(data)]
        if let row { body["version"] = .number(Double(row.version)) }
        let _: Row = try await request("records/" + module + (row.map { "/" + $0.id } ?? ""), method: row == nil ? "POST" : "PUT", body: body)
        revision += 1
    }
    func remove(_ module: String, row: Row) async throws {
        let _: [String: Value] = try await request("records/\(module)/\(row.id)", method: "DELETE", body: ["version": .number(Double(row.version))])
        revision += 1
    }
    func options(kind: String) async throws -> [Choice] {
        if kind == "user" {
            let rows: [[String: Value]] = try await request("directory")
            return rows.compactMap { r in guard let id = r["id"], let name = r["name"] else { return nil }; return Choice(id: id.text, name: name.text) }
        }
        if kind == "book" {
            let rows: [Row] = try await request("records/books")
            return rows.map { Choice(id: $0.id, name: $0.data["title"]?.text ?? $0.id) }
        }
        let roster: [String: Value] = try await request("roster")
        guard case .array(let rows) = roster[kind == "student" ? "students" : "classes"] else { return [] }
        return rows.compactMap { row in
            guard case .object(let r) = row, let id = r["id"], let name = r["name"] else { return nil }
            return Choice(id: id.text, name: name.text)
        }
    }
    func connect() {
        listener?.cancel(); socket?.cancel(with: .goingAway, reason: nil)
        guard let base, !token.isEmpty else { return }
        var components = URLComponents(url: base.appendingPathComponent("ws"), resolvingAgainstBaseURL: false)!
        components.scheme = "wss"
        var request = URLRequest(url: components.url!)
        request.setValue("Bearer " + token, forHTTPHeaderField: "Authorization")
        let task = transport.webSocketTask(with: request); socket = task; task.resume()
        connection = "Łączenie…"
        listener = Task { [weak self] in
            while !Task.isCancelled {
                do {
                    let message = try await task.receive()
                    guard let self else { return }
                    self.connection = "Połączono"
                    let data: Data
                    switch message { case .data(let d): data = d; case .string(let s): data = Data(s.utf8); @unknown default: continue }
                    let event = try? JSONDecoder().decode([String: Value].self, from: data)
                    if event?["type"]?.text != "pong" { self.revision += 1 }
                } catch {
                    guard !Task.isCancelled, let self else { return }
                    self.connection = "Brak synchronizacji — odśwież ręcznie"
                    return
                }
            }
        }
        // Application ping makes the backend recheck session validity immediately.
        Task { try? await task.send(.string("ping")) }
    }
    func logout() async {
        let _: [String: Value]? = try? await request("auth/logout", method: "POST")
        clear()
    }
    private func clear() {
        listener?.cancel(); listener = nil; socket?.cancel(with: .goingAway, reason: nil); socket = nil
        token = ""; profile = nil; connection = "Rozłączono"; base = nil
    }
}
